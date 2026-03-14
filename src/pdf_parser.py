"""
pdf_parser.py
-------------
Extracts text and images from PDF files using PyMuPDF (fitz).
Handles both inspection reports and thermal image reports.

Enhanced features:
- Table-aware text extraction preserves tabular data structure
- OCR fallback for scanned / image-only pages
- Text normalization (whitespace, encoding artifacts)
- Image context tagging with surrounding text
"""

import fitz  # PyMuPDF
import os
import io
import re
from PIL import Image

from src.logger import get_logger, PipelineTimer

logger = get_logger("pdf_parser")


def _normalize_text(text: str) -> str:
    """
    Clean up extracted PDF text:
    - Fix common encoding artifacts (ligatures, smart quotes, etc.)
    - Collapse runs of whitespace while preserving paragraph breaks
    - Strip trailing whitespace from each line
    """
    if not text:
        return ""

    # Fix common encoding artifacts
    replacements = {
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "--",
        "\u2026": "...",
        "\u00a0": " ",      # non-breaking space
        "\u200b": "",       # zero-width space
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Collapse excessive blank lines (3+ newlines → 2)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip trailing whitespace per line
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    return text.strip()


def _extract_tables_from_page(page) -> str:
    """
    Extract tabular data from a page using PyMuPDF's table finder.
    Returns formatted text representation of any tables found.
    """
    table_texts = []
    try:
        tables = page.find_tables()
        for table in tables:
            extracted = table.extract()
            if not extracted:
                continue

            # Format table rows preserving structure
            formatted_rows = []
            for row in extracted:
                # Replace None with empty string
                cleaned = [str(cell).strip() if cell else "" for cell in row]
                formatted_rows.append(" | ".join(cleaned))

            if formatted_rows:
                table_texts.append("\n".join(formatted_rows))
    except Exception as e:
        logger.debug("Table extraction failed on page: %s", e)

    return "\n\n".join(table_texts)


def _is_scanned_page(page) -> bool:
    """
    Detect if a page is likely scanned (image-only, no selectable text).
    """
    text = page.get_text("text").strip()
    images = page.get_images(full=True)
    # If very little text but has images, it's likely scanned
    return len(text) < 20 and len(images) > 0


def _ocr_page(page) -> str:
    """
    Attempt OCR on a scanned page by rendering to pixmap
    and using PyMuPDF's built-in OCR if available, otherwise
    return a placeholder.
    """
    try:
        # Try PyMuPDF's built-in OCR (requires Tesseract)
        tp = page.get_textpage_ocr(flags=fitz.TEXT_PRESERVE_WHITESPACE)
        text = page.get_text("text", textpage=tp)
        if text.strip():
            return text
    except Exception:
        pass

    # Fallback: note that the page is image-only
    return "[OCR UNAVAILABLE — This page contains images without extractable text]\n"


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract all text content from a PDF file with enhanced accuracy.

    Features:
    - Regular text extraction with layout preservation
    - Table structure extraction (preserves columns/rows)
    - OCR fallback for scanned pages
    - Text normalization

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Concatenated, normalized text from all pages
    """
    text_content = []

    try:
        doc = fitz.open(pdf_path)
        pdf_name = os.path.basename(pdf_path)
        logger.info("Parsing PDF: %s (%d pages)", pdf_name, len(doc))

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_texts = []

            # Check if page is scanned
            if _is_scanned_page(page):
                logger.info("  Page %d: scanned/image-only — attempting OCR", page_num + 1)
                ocr_text = _ocr_page(page)
                page_texts.append(ocr_text)
            else:
                # Standard text extraction
                text = page.get_text("text")
                if text.strip():
                    page_texts.append(text)

                # Also extract any tables on the page
                table_text = _extract_tables_from_page(page)
                if table_text.strip():
                    page_texts.append(f"\n[TABLE DATA]\n{table_text}\n[END TABLE]\n")

            if any(t.strip() for t in page_texts):
                combined = "\n".join(page_texts)
                text_content.append(f"--- Page {page_num + 1} ---\n{combined}")

        doc.close()
        logger.info("Extracted text from %d pages of %s", len(text_content), pdf_name)

    except Exception as e:
        raise RuntimeError(f"Failed to extract text from {pdf_path}: {str(e)}")

    raw_text = "\n\n".join(text_content)
    return _normalize_text(raw_text)


def extract_images_from_pdf(pdf_path: str, output_dir: str = None, max_images: int = 20) -> list:
    """
    Extract embedded images from a PDF file.

    Enhanced: tags each image with surrounding text context for better
    correlation during report generation.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted images (optional)
        max_images: Maximum number of images to extract

    Returns:
        List of image dicts with PIL Image, metadata, and text context
    """
    images = []

    try:
        doc = fitz.open(pdf_path)
        image_count = 0
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]

        for page_num in range(len(doc)):
            if image_count >= max_images:
                break

            page = doc[page_num]
            page_text = page.get_text("text")
            image_list = page.get_images(full=True)

            for img_index, img_ref in enumerate(image_list):
                if image_count >= max_images:
                    break

                try:
                    xref = img_ref[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]

                    # Convert to PIL Image
                    pil_img = Image.open(io.BytesIO(image_bytes))

                    # Skip very small images (icons/decorations)
                    if pil_img.width < 100 or pil_img.height < 100:
                        continue

                    # Build a short context snippet from surrounding text
                    context_snippet = ""
                    if page_text.strip():
                        # Take first 200 chars as context for this page's images
                        context_snippet = page_text.strip()[:200].replace("\n", " ")

                    img_data = {
                        "image": pil_img,
                        "page": page_num + 1,
                        "index": img_index,
                        "ext": image_ext,
                        "context": context_snippet,
                        "source": pdf_name,
                    }

                    # Save to disk if output_dir provided
                    if output_dir:
                        os.makedirs(output_dir, exist_ok=True)
                        img_filename = f"{pdf_name}_page{page_num+1}_img{img_index}.{image_ext}"
                        img_path = os.path.join(output_dir, img_filename)
                        pil_img.save(img_path)
                        img_data["saved_path"] = img_path

                    images.append(img_data)
                    image_count += 1

                except Exception as e:
                    logger.debug("Skipping problematic image on page %d: %s", page_num + 1, e)
                    continue

        doc.close()
        logger.info("Extracted %d images from %s", len(images), pdf_name)

    except Exception as e:
        raise RuntimeError(f"Failed to extract images from {pdf_path}: {str(e)}")

    return images


def parse_pdf(pdf_path: str, image_output_dir: str = None) -> dict:
    """
    Full PDF parsing: extracts both text and images.

    Args:
        pdf_path: Path to the PDF file
        image_output_dir: Directory to save extracted images

    Returns:
        Dictionary with 'text', 'images', 'source', 'num_images', 'num_pages'
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    with PipelineTimer(f"PDF parse: {os.path.basename(pdf_path)}", logger):
        text = extract_text_from_pdf(pdf_path)
        images = extract_images_from_pdf(pdf_path, output_dir=image_output_dir)

    return {
        "text": text,
        "images": images,
        "source": os.path.basename(pdf_path),
        "num_images": len(images),
        "num_pages": len(fitz.open(pdf_path)),
    }
