"""
ddr_generator.py
----------------
Generates the Detailed Diagnostic Report (DDR) using Gemini.
Uses retrieved context from the RAG pipeline to ground the LLM response.

Enhanced features:
- Pre-generation context validation (coverage check)
- Post-generation output validation (section completeness, dedup)
- Post-processing for consistent formatting
- Increased token limit to prevent truncation
- Structured logging throughout
"""

import os
import re
import time
from datetime import datetime
from dotenv import load_dotenv
import google.generativeai as genai

from src.logger import get_logger, PipelineTimer

load_dotenv()

logger = get_logger("ddr_generator")

# Models to try in order — if one hits rate limits, try the next
FALLBACK_MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
]

# Required sections in the DDR output
REQUIRED_SECTIONS = [
    "INSPECTION DETAILS",
    "SECTION 1",
    "SECTION 2",
    "SECTION 3",
    "SECTION 4",
    "SECTION 5",
    "SECTION 6",
    "SECTION 7",
]


def load_prompt_template(prompt_path: str = None) -> str:
    """Load the DDR prompt template from file."""
    if prompt_path and os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    # Built-in fallback template (same structure as prompts/ddr_prompt.txt)
    return _get_builtin_prompt()


def _get_builtin_prompt() -> str:
    """Built-in fallback DDR prompt template."""
    return """You are a structural inspection expert and building diagnostics specialist.

Using ONLY the inspection data and thermal analysis data provided below in the Context section, generate a professional Detailed Diagnostic Report (DDR).

STRICT RULES:
- Do NOT invent, assume, or extrapolate any facts not present in the context.
- Merge duplicate observations — do not repeat the same issue multiple times.
- If any information is missing or unclear, explicitly write "Not Available — [specific reason what data is missing]".
- Use simple, client-friendly language.
- If there is a conflict between inspection data and thermal data, present BOTH findings with a [CONFLICT] marker and explain the discrepancy.
- For each area, you MUST cross-reference inspection observations with thermal readings for the same location.
- Before writing each section, check if you have sufficient data. If not, state what document data would be needed.
- You MUST use the exact SECTION headings below so the PDF parser can read them. Do not change the numbering or naming of the SECTIONS.

CONTEXT FROM INSPECTION AND THERMAL DOCUMENTS:
{retrieved_context}

Generate the DDR with exactly these sections and sub-sections:

INSPECTION DETAILS
Customer Name / Property: [Extract or Not Available]
Case No: [Extract or Not Available]
Date of Inspection: [Extract or Not Available]
Time of Inspection: [Extract or Not Available]
Inspected By: [Extract or Not Available]
Type of Structure: [Extract or Not Available]
Number of Floors: [Extract or Not Available]
Year of Construction: [Extract or Not Available]
Age of Building: [Extract or Not Available]
Previous Structure Audit Done: [Extract or Not Available]
Previous Repairs: [Extract or Not Available]

==========

SECTION 1: INTRODUCTION
1.1 BACKGROUND
[Text...]
1.2 OBJECTIVE OF THE HEALTH ASSESSMENT
[Text...]
1.3 SCOPE OF WORK
[Text...]

==========

SECTION 2: GENERAL INFORMATION AND SUMMARY
[Summary of the issues found...]

==========

SECTION 3: VISUAL OBSERVATION AND READINGS
AREA 1: [Name of Area]
Negative Side (Impacted Location): [Value]
Positive Side (Source Location): [Value]
Thermal Reading: [Value]
Leakage Pattern: [Value]

==========

SECTION 4: STRUCTURAL CONDITION ASSESSMENTS
4.1 TERRACE CONDITION ASSESSMENT
1. [Component Name]: [Good/Moderate/Poor] - [Remarks]
4.2 RCC MEMBERS CONDITION
1. [Component Name]: [Good/Moderate/Poor] - [Remarks]
4.3 EXTERIOR WALL CONDITION
1. [Component Name]: [Good/Moderate/Poor] - [Remarks]

==========

SECTION 5: ANALYSIS & SUGGESTIONS
5.1 BATHROOM AND BALCONY GROUTING TREATMENT
5.2 PLUMBING
5.3 TERRACE WATERPROOFING TREATMENT
5.4 EXTERNAL WALL TREATMENT
5.5 PLASTER WORK
5.6 RCC MEMBERS TREATMENT

==========

SECTION 6: SUMMARY TABLE AND ACTIONS
OVERALL SEVERITY: [High/Moderate/Low]
SUMMARY OF IMPACTED AREAS VS EXPOSED SOURCES
PRIORITY ACTIONS
IMMEDIATE:
- [Action]
SHORT-TERM:
- [Action]
LONG-TERM:
- [Action]

==========

SECTION 7: LIMITATION AND PRECAUTION NOTE
7.1 ADDITIONAL OBSERVATIONS
[Any other notes]
7.2 MISSING OR UNCLEAR INFORMATION
[List what was missing from the provided docs]

END OF DETAILED REPORT
"""


def _validate_context(context: str) -> dict:
    """
    Pre-generation validation: analyze retrieved context for coverage.
    Returns a coverage report dict.
    """
    report = {
        "total_length": len(context),
        "has_inspection_data": "inspection" in context.lower(),
        "has_thermal_data": "thermal" in context.lower(),
        "has_area_data": bool(re.search(r"(?i)area|room|bedroom|kitchen|bathroom|hall|balcony", context)),
        "has_structural_data": bool(re.search(r"(?i)RCC|beam|column|slab|structural", context)),
        "has_checklist_data": bool(re.search(r"(?i)checklist|score|rating", context)),
        "warnings": [],
    }

    if not report["has_inspection_data"]:
        report["warnings"].append("No inspection report data found in context")
    if not report["has_thermal_data"]:
        report["warnings"].append("No thermal report data found in context")
    if report["total_length"] < 500:
        report["warnings"].append(f"Context is very short ({report['total_length']} chars) — report may be thin")

    for w in report["warnings"]:
        logger.warning("Context validation: %s", w)

    return report


def _robust_deduplicate(text: str) -> str:
    """
    Aggressively deduplicate DDR text by parsing it into semantic blocks.
    Ensures that headers like "SECTION 1...", "1.1 BACKGROUND" only ever
    appear once, and removes trailing junk from duplicated blocks.
    """
    # 1. Split into major sections
    section_blocks = re.split(r"(={5,})", text)
    
    seen_major_sections = set()
    cleaned_blocks = []

    for block in section_blocks:
        if bool(re.match(r"={5,}", block.strip())):
            cleaned_blocks.append(block)
            continue

        # Detect the major section header (e.g., "SECTION 1: INTRODUCTION")
        sec_match = re.search(r"^(SECTION\s+\d+\s*:.*?)(?:\n|$)", block.strip(), re.IGNORECASE)
        if sec_match:
            sec_header = re.sub(r"\s+", " ", sec_match.group(1).strip().upper())
            if sec_header in seen_major_sections:
                logger.info("Discarding repeated major section: %s", sec_header)
                continue
            seen_major_sections.add(sec_header)

        # 2. Line-by-line deduplication within the block for sub-sections
        lines = block.split('\n')
        seen_subsections = set()
        cleaned_lines = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            upper_line = re.sub(r"\s+", " ", line.strip().upper())
            
            # Match subsection headers like "1.1 BACKGROUND"
            sub_match = re.match(r"^(\d+\.\d+\s+[A-Z][A-Z\s&]+?)$", upper_line)
            
            if sub_match:
                sub_header = sub_match.group(1)
                if sub_header in seen_subsections:
                    logger.info("Discarding repeated sub-section: %s", sub_header)
                    # Skip until we hit a new sub-section or the end
                    i += 1
                    while i < len(lines):
                        next_upper = re.sub(r"\s+", " ", lines[i].strip().upper())
                        if re.match(r"^(\d+\.\d+\s+[A-Z][A-Z\s&]+?)$", next_upper) and next_upper not in seen_subsections:
                            i -= 1 # backtrack so next loop iteration picks it up
                            break
                        i += 1
                else:
                    seen_subsections.add(sub_header)
                    # Sometimes the LLM prepends "INTRODUCTION\n" right before "1.1 BACKGROUND" on a repeat.
                    # We can't safely strip all preceding text without risking valid data, 
                    # but since the whole major section is tracked, it's safer.
                    cleaned_lines.append(line)
            else:
                # Also deduplicate standalone duplicate lines (e.g. repeated "INTRODUCTION")
                # if they are literally identical to the last appended valid line
                if line.strip() and cleaned_lines and line.strip() == cleaned_lines[-1].strip():
                    pass # skip instant duplicate lines
                else:
                    cleaned_lines.append(line)
            i += 1

        cleaned_blocks.append("\n".join(cleaned_lines))

    return "".join(cleaned_blocks)


def _post_process_ddr(ddr_text: str) -> str:
    """
    Post-process the generated DDR for consistency and clarity:
    - Remove repeated SECTION blocks and sub-sections via robust parser
    - Normalize section dividers
    - Ensure consistent severity terminology
    - Clean up formatting artifacts
    """
    if not ddr_text:
        return ddr_text

    # Remove markdown formatting artifacts that Gemini sometimes adds
    text = ddr_text
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # Remove bold markers
    text = re.sub(r"#{1,3}\s+", "", text)             # Remove markdown heading markers

    # Normalize section dividers — ensure consistent === format
    text = re.sub(r"={5,}", "==========", text)

    # ── KEY FIX: Remove duplicated sections and sub-sections ──
    text = _robust_deduplicate(text)

    # Normalize severity terms
    severity_map = {
        r"\bhigh\s*severity\b": "High",
        r"\bmoderate\s*severity\b": "Moderate",
        r"\blow\s*severity\b": "Low",
    }
    for pattern, replacement in severity_map.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Remove duplicate blank lines (3+ → 2)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Ensure "END OF DETAILED REPORT" is present
    if "END OF DETAILED REPORT" not in text:
        text = text.rstrip() + "\n\nEND OF DETAILED REPORT"

    return text.strip()


def _validate_output(ddr_text: str) -> dict:
    """
    Post-generation validation: check that the DDR has all required sections.
    Returns a validation report dict.
    """
    report = {
        "sections_found": [],
        "sections_missing": [],
        "total_words": len(ddr_text.split()),
        "warnings": [],
    }

    for section in REQUIRED_SECTIONS:
        if section.lower() in ddr_text.lower():
            report["sections_found"].append(section)
        else:
            report["sections_missing"].append(section)

    if report["sections_missing"]:
        report["warnings"].append(
            f"Missing sections: {report['sections_missing']}"
        )

    if report["total_words"] < 200:
        report["warnings"].append(
            f"Report is very short ({report['total_words']} words)"
        )

    # Check for conflict markers
    conflict_count = len(re.findall(r"\[CONFLICT\]", ddr_text))
    report["conflicts_flagged"] = conflict_count

    # Check for "Not Available" markers
    na_count = len(re.findall(r"Not Available", ddr_text))
    report["not_available_count"] = na_count

    for w in report["warnings"]:
        logger.warning("Output validation: %s", w)

    logger.info(
        "DDR output: %d words, %d sections found, %d missing, %d conflicts, %d N/A markers",
        report["total_words"],
        len(report["sections_found"]),
        len(report["sections_missing"]),
        conflict_count,
        na_count,
    )

    return report


def generate_ddr(
    retrieved_context: str,
    api_key: str = None,
    prompt_template_path: str = None,
    model_name: str = "gemini-2.0-flash-lite",
    images: list = None,
) -> str:
    """
    Generate the DDR report using Gemini with retrieved context.
    Automatically retries with fallback models if rate-limited.

    Enhanced with:
    - Pre-generation context validation
    - Post-generation output validation
    - Post-processing for clean formatting
    - Increased token limit (8192)
    """
    key = api_key or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GOOGLE_API_KEY not found.")

    genai.configure(api_key=key)

    # Pre-validate context
    context_report = _validate_context(retrieved_context)
    logger.info("Context coverage: %s", {k: v for k, v in context_report.items() if k != "warnings"})

    # Load prompt template
    prompt_template = load_prompt_template(prompt_template_path)

    # Fill in the context
    if "{retrieved_context}" in prompt_template:
        full_prompt = prompt_template.replace("{retrieved_context}", retrieved_context)
    else:
        full_prompt = prompt_template + f"\n\nCONTEXT:\n{retrieved_context}"

    # Inject coverage warnings into prompt so the LLM is aware
    if context_report["warnings"]:
        warnings_text = "\n".join(f"- {w}" for w in context_report["warnings"])
        full_prompt += (
            f"\n\n[SYSTEM NOTE — DATA GAPS DETECTED]\n{warnings_text}\n"
            "For any section affected by missing data, explicitly write "
            "'Not Available — [reason]' and describe what document data would be needed.\n"
        )

    # Configure Gemini model
    generation_config = genai.GenerationConfig(
        temperature=0.1,
        max_output_tokens=8192,  # Increased from 4096 to prevent truncation
        top_p=0.95,
    )

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    # Build model fallback list
    models_to_try = [model_name] + [m for m in FALLBACK_MODELS if m != model_name]

    last_error = None
    for current_model in models_to_try:
        for attempt in range(3):
            try:
                logger.info("Trying model: %s (attempt %d)", current_model, attempt + 1)

                model = genai.GenerativeModel(
                    model_name=current_model,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                )

                # Build multimodal payload if images are provided
                payload = [full_prompt]
                if images:
                    for img_dict in images:
                        pil_img = img_dict.get("image")
                        src = img_dict.get("source", "PDF")
                        pg = img_dict.get("page", "?")
                        idx = img_dict.get("index", "0")
                        context = img_dict.get("context", "")

                        if pil_img:
                            img_id = f"{src}_Page{pg}_Index{idx}".replace(" ", "_")
                            # Include context so the LLM can match images to areas
                            context_hint = f" | Page context: {context[:150]}" if context else ""
                            payload.append(f"Image ID: {img_id}{context_hint}")
                            payload.append(pil_img)

                with PipelineTimer(f"LLM Generation ({current_model})", logger):
                    response = model.generate_content(payload)

                if not response.text:
                    raise RuntimeError("Gemini returned an empty response.")

                logger.info("Success with model: %s", current_model)

                # Post-process and validate
                cleaned = _post_process_ddr(response.text)
                output_report = _validate_output(cleaned)

                return cleaned

            except Exception as e:
                last_error = e
                error_str = str(e)
                if "429" in error_str or "quota" in error_str.lower() or "rate" in error_str.lower():
                    delay = 20 * (attempt + 1)
                    logger.warning("Rate limited on %s, waiting %ds...", current_model, delay)
                    time.sleep(delay)
                    continue
                elif "404" in error_str or "not found" in error_str.lower():
                    logger.info("Model %s not available, trying next...", current_model)
                    break
                else:
                    raise

    raise RuntimeError(
        f"All models exhausted their free-tier quota. Last error: {last_error}\n"
        "Please wait a few minutes and try again, or use a paid API key."
    )


def save_ddr_to_file(ddr_text: str, output_path: str = None) -> str:
    """Save the generated DDR to a text file."""
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"output/final_ddr_{timestamp}.txt"

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ddr_text)

    logger.info("DDR saved to: %s", output_path)
    return output_path


def generate_full_ddr(
    retriever,
    api_key: str = None,
    prompt_template_path: str = None,
    save_output: bool = True,
    output_dir: str = "output",
    images: list = None,
) -> dict:
    """
    Full DDR generation workflow: retrieve context → generate DDR → save.

    Enhanced with:
    - Context coverage validation before generation
    - Output validation after generation
    - Pipeline metrics collection
    """
    # Step 1: Retrieve comprehensive context
    with PipelineTimer("Context Retrieval", logger) as t:
        context = retriever.retrieve_for_ddr(top_k_per_query=5)

    if not context.strip():
        raise ValueError("No context could be retrieved. Check if the pipeline is built.")

    logger.info("Retrieved context: %d characters", len(context))

    # Step 2: Generate DDR with Gemini
    ddr_text = generate_ddr(
        retrieved_context=context,
        api_key=api_key,
        prompt_template_path=prompt_template_path,
        images=images,
    )

    # Step 3: Optionally save to file and PDF
    saved_txt_path = None
    saved_pdf_path = None
    if save_output:
        os.makedirs(output_dir, exist_ok=True)
        txt_path = os.path.join(output_dir, "final_ddr.txt")
        saved_txt_path = save_ddr_to_file(ddr_text, txt_path)

        # Generate PDF
        try:
            from src.pdf_generator import save_ddr_pdf

            pdf_path = os.path.join(output_dir, "final_ddr.pdf")
            saved_pdf_path = save_ddr_pdf(ddr_text, pdf_path)
        except Exception as e:
            logger.warning("PDF generation failed: %s", e)

    return {
        "ddr_text": ddr_text,
        "saved_path": saved_txt_path,
        "pdf_path": saved_pdf_path,
        "context_length": len(context),
    }
