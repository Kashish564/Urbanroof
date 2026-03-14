"""
chunking.py
-----------
Splits extracted PDF text into overlapping chunks suitable for embedding.

Enhanced features:
- Section-aware chunking: detects inspection/thermal section headers and
  keeps logical sections together as single chunks where possible
- Each chunk carries a `section_type` metadata tag for downstream filtering
- Falls back to sliding-window for large sections
"""

import re


# ── Section detection patterns ────────────────────────────────────────────
# These patterns match common headings found in inspection and thermal PDFs.
SECTION_PATTERNS = [
    (r"(?i)\b(?:inspection details|property details|client details)\b", "inspection_metadata"),
    (r"(?i)\b(?:thermal\s+(?:reading|analysis|image|scan|report|data))", "thermal_reading"),
    (r"(?i)\b(?:observation|visual\s+observation|area\s+observation)", "observation"),
    (r"(?i)\b(?:checklist|inspection\s+checklist|score)", "checklist"),
    (r"(?i)\b(?:RCC|structural|beam|column|slab)", "structural"),
    (r"(?i)\b(?:plumbing|drainage|pipe|concealed)", "plumbing"),
    (r"(?i)\b(?:terrace|waterproof|roof)", "terrace"),
    (r"(?i)\b(?:bathroom|toilet|balcony|kitchen)", "wet_area"),
    (r"(?i)\b(?:external\s+wall|exterior|facade|crack)", "exterior"),
    (r"(?i)\b(?:severity|priority|action|recommendation)", "severity_action"),
    (r"(?i)\b(?:summary|conclusion|finding)", "summary"),
    (r"\[TABLE DATA\]", "table_data"),
]


def _classify_section(text: str) -> str:
    """
    Classify a chunk of text into a section_type based on keyword patterns.
    Returns the first matching type or 'general'.
    """
    for pattern, section_type in SECTION_PATTERNS:
        if re.search(pattern, text[:500]):  # Check first 500 chars for speed
            return section_type
    return "general"


def _detect_section_boundaries(text: str) -> list:
    """
    Detect natural section boundaries in PDF text.
    Looks for:
    - Page markers (--- Page N ---)
    - ALL-CAPS headings (at least 3 uppercase words)
    - Numbered section headers (e.g. "3.1 TERRACE CONDITION")
    - Table markers ([TABLE DATA] ... [END TABLE])

    Returns list of (start_pos, end_pos, header_text) tuples.
    """
    boundaries = []

    # Pattern for section-like headers
    header_pattern = re.compile(
        r"^("
        r"--- Page \d+ ---"                    # Page markers
        r"|[A-Z][A-Z\s&/]{8,}"                 # ALL-CAPS headings (min 8 chars)
        r"|\d+\.\d*\s+[A-Z][A-Z\s&/]{5,}"     # Numbered headings like "3.1 TERRACE..."
        r"|AREA \d+:"                           # Area markers
        r"|\[TABLE DATA\]"                      # Table markers
        r")",
        re.MULTILINE,
    )

    matches = list(header_pattern.finditer(text))

    if not matches:
        return [(0, len(text), "")]

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        boundaries.append((start, end, m.group().strip()))

    # Include any text before the first header
    if matches and matches[0].start() > 0:
        boundaries.insert(0, (0, matches[0].start(), ""))

    return boundaries


def chunk_text(text: str, chunk_size: int = 800, chunk_overlap: int = 150) -> list:
    """
    Split text into overlapping chunks for RAG retrieval.
    Uses section-aware splitting first, then falls back to sliding window
    for sections that exceed chunk_size.

    Args:
        text: Full text to chunk
        chunk_size: Maximum characters per chunk
        chunk_overlap: Number of characters to overlap between chunks

    Returns:
        List of text chunk strings
    """
    if not text or not text.strip():
        return []

    chunks = []

    # First pass: detect section boundaries
    sections = _detect_section_boundaries(text)

    for start, end, header in sections:
        section_text = text[start:end].strip()
        if not section_text:
            continue

        # If section fits in one chunk, keep it whole
        if len(section_text) <= chunk_size:
            chunks.append(section_text)
        else:
            # Fall back to sliding window for large sections
            sub_chunks = _sliding_window_chunk(section_text, chunk_size, chunk_overlap)
            chunks.extend(sub_chunks)

    return chunks


def _sliding_window_chunk(text: str, chunk_size: int, chunk_overlap: int) -> list:
    """Sliding window chunking with smart boundary detection."""
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + chunk_size, text_length)

        # Try to break at a natural boundary
        if end < text_length:
            break_search_start = max(start, end - 100)

            # Prefer paragraph breaks
            para_break = text.rfind("\n\n", break_search_start, end)
            if para_break > start:
                end = para_break
            else:
                # Fall back to sentence breaks
                sent_break = max(
                    text.rfind(". ", break_search_start, end),
                    text.rfind(".\n", break_search_start, end),
                )
                if sent_break > start:
                    end = sent_break + 1

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move forward with overlap
        start = end - chunk_overlap if end < text_length else text_length

        # Prevent infinite loop
        if start >= end:
            start = end

    return chunks


def chunk_documents(documents: list, chunk_size: int = 800, chunk_overlap: int = 150) -> list:
    """
    Chunk multiple documents and tag each chunk with source and section type.
    Deduplicates highly similar chunks to prevent index bloat and LLM repetition.

    Args:
        documents: List of dicts with 'text' and 'source' keys
        chunk_size: Maximum characters per chunk
        chunk_overlap: Overlap between chunks

    Returns:
        List of dicts with 'text', 'source', 'chunk_id', 'section_type' keys
    """
    import hashlib
    all_chunks = []
    seen_fingerprints = set()

    for doc in documents:
        source = doc.get("source", "unknown")
        text = doc.get("text", "")

        chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        for i, chunk in enumerate(chunks):
            # Create a whitespace-normalized fingerprint for deduplication
            normalized_chunk = re.sub(r"\s+", " ", chunk.strip().lower())
            fingerprint = hashlib.md5(normalized_chunk.encode('utf-8')).hexdigest()

            if fingerprint in seen_fingerprints:
                continue
            
            seen_fingerprints.add(fingerprint)
            section_type = _classify_section(chunk)
            
            all_chunks.append({
                "text": chunk,
                "source": source,
                "chunk_id": f"{source}_chunk_{i}",
                "chunk_index": i,
                "total_chunks": len(chunks),
                "section_type": section_type,
            })

    return all_chunks
