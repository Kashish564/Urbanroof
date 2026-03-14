"""
pdf_generator.py — Generate UrbanRoof-styled DDR PDF from report text.

Uses reportlab to produce a professional PDF matching the UrbanRoof
Detailed Diagnosis Report visual style: dark header, yellow/green accents,
section dividers, and clean table formatting.
"""

import io
import re
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, KeepTogether
)
from reportlab.platypus.flowables import Flowable


# ── Brand colours ──────────────────────────────────────────────────────────
DARK_BG    = colors.HexColor("#2B2B2B")
YELLOW     = colors.HexColor("#F5A800")
GREEN      = colors.HexColor("#4CAF50")
WHITE      = colors.white
LIGHT_GRAY = colors.HexColor("#F5F5F5")
MID_GRAY   = colors.HexColor("#CCCCCC")
DARK_GRAY  = colors.HexColor("#444444")
HEADER_BLK = colors.HexColor("#1A1A1A")
GOOD_GREEN = colors.HexColor("#4CAF50")
MOD_ORANGE = colors.HexColor("#F5A800")
POOR_RED   = colors.HexColor("#E53935")
TABLE_HDR  = colors.HexColor("#222222")
ROW_ALT    = colors.HexColor("#F9F9F9")


# ── Custom page template with header/footer ─────────────────────────────────
class DDRPageTemplate:
    def __init__(self, property_address="", report_id=""):
        self.property_address = property_address
        self.report_id = report_id

    def on_page(self, canvas, doc):
        canvas.saveState()
        width, height = A4

        # ── Top dark header bar ──
        canvas.setFillColor(DARK_BG)
        canvas.rect(0, height - 22*mm, width, 22*mm, fill=1, stroke=0)

        # Green accent line
        canvas.setFillColor(GREEN)
        canvas.rect(0, height - 23*mm, width, 1*mm, fill=1, stroke=0)

        # Report label in header
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(15*mm, height - 10*mm, "IR-, Detailed Diagnosis Report of")
        canvas.setFont("Helvetica", 7.5)
        addr_short = self.property_address[:70] + ("..." if len(self.property_address) > 70 else "")
        canvas.drawString(15*mm, height - 16*mm, addr_short)

        # UrbanRoof logo text (right side)
        canvas.setFillColor(YELLOW)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawRightString(width - 15*mm, height - 12*mm, "UrbanRoof")

        # ── Bottom footer bar ──
        canvas.setFillColor(GREEN)
        canvas.rect(0, 12*mm, width, 0.5*mm, fill=1, stroke=0)

        canvas.setFillColor(YELLOW)
        canvas.setFont("Helvetica-Oblique", 7)
        canvas.drawString(15*mm, 7*mm, "www.urbanroof.in")

        canvas.setFillColor(YELLOW)
        canvas.setFont("Helvetica-BoldOblique", 7)
        canvas.drawCentredString(width / 2, 7*mm, "UrbanRoof Private Limited")

        canvas.setFillColor(DARK_GRAY)
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(width - 15*mm, 7*mm, f"Page {doc.page}")

        canvas.restoreState()

    def on_first_page(self, canvas, doc):
        # First page: full dark cover header
        self.on_page(canvas, doc)


# ── Style helpers ────────────────────────────────────────────────────────────
def _build_styles():
    base = getSampleStyleSheet()

    styles = {
        "cover_title": ParagraphStyle("cover_title",
            fontName="Helvetica-Bold", fontSize=28,
            textColor=WHITE, alignment=TA_CENTER, spaceAfter=6),

        "cover_subtitle": ParagraphStyle("cover_subtitle",
            fontName="Helvetica", fontSize=11,
            textColor=YELLOW, alignment=TA_CENTER, spaceAfter=4),

        "cover_label": ParagraphStyle("cover_label",
            fontName="Helvetica-Bold", fontSize=9,
            textColor=YELLOW, spaceAfter=2),

        "cover_value": ParagraphStyle("cover_value",
            fontName="Helvetica", fontSize=9,
            textColor=WHITE, spaceAfter=8),

        "section_heading": ParagraphStyle("section_heading",
            fontName="Helvetica-Bold", fontSize=13,
            textColor=YELLOW, spaceBefore=12, spaceAfter=4),

        "sub_heading": ParagraphStyle("sub_heading",
            fontName="Helvetica-Bold", fontSize=10,
            textColor=DARK_GRAY, spaceBefore=8, spaceAfter=3),

        "area_heading": ParagraphStyle("area_heading",
            fontName="Helvetica-Bold", fontSize=10,
            textColor=WHITE, spaceBefore=6, spaceAfter=2,
            backColor=DARK_BG, leftIndent=4, rightIndent=4),

        "label": ParagraphStyle("label",
            fontName="Helvetica-Bold", fontSize=8.5,
            textColor=DARK_GRAY, spaceAfter=1),

        "body": ParagraphStyle("body",
            fontName="Helvetica", fontSize=8.5,
            textColor=colors.black, spaceAfter=4, leading=13),

        "bullet": ParagraphStyle("bullet",
            fontName="Helvetica", fontSize=8.5,
            textColor=colors.black, leftIndent=12,
            bulletIndent=4, spaceAfter=2, leading=12),

        "detail_label": ParagraphStyle("detail_label",
            fontName="Helvetica-Bold", fontSize=8.5,
            textColor=DARK_GRAY, spaceAfter=1),

        "detail_value": ParagraphStyle("detail_value",
            fontName="Helvetica", fontSize=8.5,
            textColor=colors.black, spaceAfter=3),

        "severity_high": ParagraphStyle("severity_high",
            fontName="Helvetica-Bold", fontSize=9,
            textColor=POOR_RED),

        "severity_mod": ParagraphStyle("severity_mod",
            fontName="Helvetica-Bold", fontSize=9,
            textColor=MOD_ORANGE),

        "severity_low": ParagraphStyle("severity_low",
            fontName="Helvetica-Bold", fontSize=9,
            textColor=GOOD_GREEN),

        "disclaimer": ParagraphStyle("disclaimer",
            fontName="Helvetica-Oblique", fontSize=7.5,
            textColor=DARK_GRAY, leading=11, spaceAfter=4),
    }
    return styles


# ── Section divider ──────────────────────────────────────────────────────────
def _section_divider(styles, title):
    elems = []
    elems.append(Spacer(1, 4*mm))
    # Dark heading bar
    data = [[Paragraph(title, ParagraphStyle("sh",
        fontName="Helvetica-Bold", fontSize=11,
        textColor=WHITE))]]
    t = Table(data, colWidths=[170*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), DARK_BG),
        ("LEFTPADDING", (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    elems.append(t)
    # Green underline
    elems.append(HRFlowable(width="100%", thickness=2, color=GREEN, spaceAfter=4))
    return elems


# ── Parse report text into sections ─────────────────────────────────────────
def _parse_report(report_text):
    """
    Split the flat report text into a dict of named sections.
    Keys: header_block, s1, s2, s3, s4, s5, s6, s7
    """
    sections = {}
    # Split on the === dividers
    parts = re.split(r"={10,}", report_text)
    full_text = report_text

    def _extract(marker_start, marker_end=None):
        """Extract text between two section markers."""
        pat_start = re.escape(marker_start)
        if marker_end:
            pat_end = re.escape(marker_end)
            m = re.search(pat_start + r"(.*?)" + pat_end, full_text, re.DOTALL | re.IGNORECASE)
        else:
            m = re.search(pat_start + r"(.*?)(?:={10,}|$)", full_text, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    # Header block — everything before SECTION 1
    m = re.search(r"INSPECTION DETAILS(.*?)SECTION 1", full_text, re.DOTALL | re.IGNORECASE)
    sections["header"] = m.group(1).strip() if m else ""

    for i in range(1, 8):
        next_i = i + 1
        start = f"SECTION {i}:"
        end = f"SECTION {next_i}:" if i < 7 else "END OF DETAILED"
        sections[f"s{i}"] = _extract(start, end)

    return sections


def _parse_key_value_block(text):
    """Parse lines like 'Key: Value' into list of (key, value) tuples."""
    pairs = []
    for line in text.strip().split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            pairs.append((k.strip(), v.strip()))
    return pairs


def _parse_areas(section3_text):
    """
    Parse AREA blocks from section 3.
    Returns list of dicts with keys: title, negative, positive, thermal, pattern
    """
    areas = []
    # Split on AREA N:
    blocks = re.split(r"(?=AREA\s+\d+:)", section3_text.strip())
    for block in blocks:
        if not block.strip() or not block.strip().startswith("AREA"):
            continue
        area = {}
        # Title
        title_m = re.match(r"AREA\s+\d+:\s*(.+)", block)
        area["title"] = title_m.group(1).strip() if title_m else "Unknown Area"

        def _field(label):
            m = re.search(re.escape(label) + r"\s*:?\s*(.*?)(?=\n[A-Z][a-z]|\n[A-Z ]+:|\Z)",
                          block, re.DOTALL | re.IGNORECASE)
            return m.group(1).strip() if m else "Not Available"

        area["negative"] = _field("Negative Side (Impacted Location)")
        area["positive"] = _field("Positive Side (Source Location)")
        area["thermal"]  = _field("Thermal Reading")
        area["pattern"]  = _field("Leakage Pattern")
        
        # Extract Image IDs (e.g., [IMAGE: Thermal_Report_Page3_Index1])
        img_markers = re.findall(r"\[IMAGE:\s*([^\]]+)\]", block)
        area["images"] = [m.strip() for m in img_markers]
        
        areas.append(area)
    return areas


# ── Cover page ───────────────────────────────────────────────────────────────
def _cover_page(story, styles, metadata):
    # Dark cover background block
    cover_data = [[""]]
    cover_table = Table(cover_data, colWidths=[170*mm], rowHeights=[60*mm])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), DARK_BG),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 5*mm))

    # Title
    story.append(Paragraph("Detailed Diagnosis Report", ParagraphStyle("ct",
        fontName="Helvetica-Bold", fontSize=24, textColor=DARK_BG,
        alignment=TA_CENTER)))
    story.append(HRFlowable(width="60%", thickness=2, color=GREEN,
                             hAlign="CENTER", spaceAfter=6))
    story.append(Spacer(1, 4*mm))

    # Date and Report ID
    story.append(Paragraph(metadata.get("report_date", datetime.today().strftime("%B %d, %Y")),
        ParagraphStyle("cd", fontName="Helvetica-Bold", fontSize=10,
                       textColor=DARK_BG)))
    story.append(Paragraph(f"Report ID: {metadata.get('report_id', 'Not Available')}",
        ParagraphStyle("cd2", fontName="Helvetica-Bold", fontSize=10,
                       textColor=DARK_BG, spaceAfter=8)))
    story.append(Spacer(1, 6*mm))

    # Two column info block
    left_data = [
        [Paragraph("Inspected & Prepared By:", ParagraphStyle("cov_lbl",
            fontName="Helvetica-Bold", fontSize=9, textColor=YELLOW)),
         Paragraph("Prepared For:", ParagraphStyle("cov_lbl2",
            fontName="Helvetica-Bold", fontSize=9, textColor=YELLOW))],
        [Paragraph(metadata.get("inspected_by", "Not Available"),
            ParagraphStyle("cov_val", fontName="Helvetica-Bold", fontSize=10,
                           textColor=DARK_BG)),
         Paragraph(metadata.get("property_address", "Not Available"),
            ParagraphStyle("cov_val2", fontName="Helvetica", fontSize=9,
                           textColor=DARK_BG))],
    ]
    info_table = Table(left_data, colWidths=[85*mm, 85*mm])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    story.append(info_table)
    story.append(PageBreak())


# ── Disclaimer page ───────────────────────────────────────────────────────────
def _disclaimer_page(story, styles):
    story.extend(_section_divider(styles, "Data and Information Disclaimer"))
    disclaimer_text = (
        "This property inspection is not an exhaustive inspection of the structure, systems, or "
        "components. The inspection may not reveal all deficiencies. A health checkup helps to reduce "
        "some of the risk involved in the property/structure & premises, but it cannot eliminate these "
        "risks, nor can the inspection anticipate future events or changes in performance due to "
        "changes in use or occupancy.\n\n"
        "An inspection addresses only those components and conditions that are present, visible, and "
        "accessible at the time of the inspection. The inspection does NOT imply insurability or "
        "warrantability of the structure or its components, although some safety issues may be "
        "addressed in this report.\n\n"
        "The inspection of this property is subject to limitations and conditions set out in this Report."
    )
    for para in disclaimer_text.split("\n\n"):
        story.append(Paragraph(para, styles["disclaimer"]))
    story.append(PageBreak())


# ── Info detail row ───────────────────────────────────────────────────────────
def _info_row(label, value, styles):
    data = [[
        Paragraph(label, styles["detail_label"]),
        Paragraph(value or "Not Available", styles["detail_value"]),
    ]]
    t = Table(data, colWidths=[55*mm, 115*mm])
    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
        ("LINEBELOW", (0,0), (-1,-1), 0.3, MID_GRAY),
    ]))
    return t


# ── Condition table (Good / Moderate / Poor) ─────────────────────────────────
def _condition_table(rows, styles):
    """
    rows: list of (sr, description, rating, remarks)
    """
    header = [
        Paragraph("Sr No", ParagraphStyle("th", fontName="Helvetica-Bold",
                  fontSize=8, textColor=WHITE, alignment=TA_CENTER)),
        Paragraph("Input Type", ParagraphStyle("th2", fontName="Helvetica-Bold",
                  fontSize=8, textColor=WHITE)),
        Paragraph("Good", ParagraphStyle("th3", fontName="Helvetica-Bold",
                  fontSize=8, textColor=GOOD_GREEN, alignment=TA_CENTER)),
        Paragraph("Moderate", ParagraphStyle("th4", fontName="Helvetica-Bold",
                  fontSize=8, textColor=MOD_ORANGE, alignment=TA_CENTER)),
        Paragraph("Poor", ParagraphStyle("th5", fontName="Helvetica-Bold",
                  fontSize=8, textColor=POOR_RED, alignment=TA_CENTER)),
        Paragraph("Remarks", ParagraphStyle("th6", fontName="Helvetica-Bold",
                  fontSize=8, textColor=WHITE)),
    ]
    data = [header]
    for i, row_text in enumerate(rows):
        # row_text format: "Description | rating | remarks"  or just plain text
        parts = row_text.split("|") if "|" in row_text else [row_text, "", ""]
        desc    = parts[0].strip() if len(parts) > 0 else row_text
        rating  = parts[1].strip().lower() if len(parts) > 1 else ""
        remarks = parts[2].strip() if len(parts) > 2 else ""

        good_mark = "✓" if "good" in rating else ""
        mod_mark  = "✓" if "moderate" in rating or "mod" in rating else ""
        poor_mark = "✓" if "poor" in rating else ""
        na_mark   = "NA" if "na" in rating or "not available" in rating else ""

        bg = ROW_ALT if i % 2 == 0 else WHITE
        row = [
            Paragraph(str(i + 1), ParagraphStyle("td", fontName="Helvetica",
                      fontSize=8, alignment=TA_CENTER)),
            Paragraph(desc, ParagraphStyle("td2", fontName="Helvetica", fontSize=8)),
            Paragraph(good_mark, ParagraphStyle("td3", fontName="Helvetica-Bold",
                      fontSize=9, textColor=GOOD_GREEN, alignment=TA_CENTER)),
            Paragraph(mod_mark, ParagraphStyle("td4", fontName="Helvetica-Bold",
                      fontSize=9, textColor=MOD_ORANGE, alignment=TA_CENTER)),
            Paragraph(poor_mark or na_mark, ParagraphStyle("td5", fontName="Helvetica-Bold",
                      fontSize=9, textColor=POOR_RED, alignment=TA_CENTER)),
            Paragraph(remarks, ParagraphStyle("td6", fontName="Helvetica",
                      fontSize=7.5, textColor=DARK_GRAY)),
        ]
        data.append(row)

    col_widths = [12*mm, 55*mm, 16*mm, 18*mm, 14*mm, 55*mm]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), TABLE_HDR),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [ROW_ALT, WHITE]),
        ("GRID", (0,0), (-1,-1), 0.3, MID_GRAY),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    return t


# ── Summary table ─────────────────────────────────────────────────────────────
def _summary_table(pairs, styles):
    """
    pairs: list of (negative_text, positive_text)
    """
    header = [
        Paragraph("Point No", ParagraphStyle("sh1", fontName="Helvetica-Bold",
                  fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)),
        Paragraph("Impacted Area (-ve side)", ParagraphStyle("sh2",
                  fontName="Helvetica-Bold", fontSize=8.5, textColor=WHITE)),
        Paragraph("Point No", ParagraphStyle("sh3", fontName="Helvetica-Bold",
                  fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)),
        Paragraph("Exposed Area (+ve side)", ParagraphStyle("sh4",
                  fontName="Helvetica-Bold", fontSize=8.5, textColor=WHITE)),
    ]
    data = [header]
    for i, (neg, pos) in enumerate(pairs):
        bg = colors.HexColor("#1E3A5F") if i % 2 == 0 else colors.HexColor("#24487A")
        data.append([
            Paragraph(str(i + 1), ParagraphStyle("sn", fontName="Helvetica-Bold",
                      fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)),
            Paragraph(neg, ParagraphStyle("sv", fontName="Helvetica",
                      fontSize=8, textColor=WHITE)),
            Paragraph(str(i + 1), ParagraphStyle("sn2", fontName="Helvetica-Bold",
                      fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)),
            Paragraph(pos, ParagraphStyle("sv2", fontName="Helvetica",
                      fontSize=8, textColor=WHITE)),
        ])

    col_widths = [16*mm, 69*mm, 16*mm, 69*mm]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), TABLE_HDR),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.HexColor("#1E3A5F"),
                                             colors.HexColor("#24487A")]),
        ("GRID", (0,0), (-1,-1), 0.3, colors.HexColor("#4A70A0")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    return t


# ── Area observation block ────────────────────────────────────────────────────
def _area_block(area, styles, index, all_images=None):
    elems = []
    # Heading bar
    title_data = [[Paragraph(f"AREA {index}: {area['title']}",
        ParagraphStyle("ah", fontName="Helvetica-Bold", fontSize=9.5, textColor=WHITE))]]
    title_table = Table(title_data, colWidths=[170*mm])
    title_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), DARK_BG),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LINEBELOW", (0,0), (-1,-1), 1.5, GREEN),
    ]))
    elems.append(KeepTogether([
        title_table,
        _info_row("Negative Side (Impacted):", area.get("negative", "Not Available"), styles),
        _info_row("Positive Side (Source):", area.get("positive", "Not Available"), styles),
        _info_row("Thermal Reading:", area.get("thermal", "Not Available"), styles),
        _info_row("Leakage Pattern:", area.get("pattern", "Not Available"), styles),
    ]))
    
    # Render associated images inline
    img_ids_to_render = area.get("images", [])
    if img_ids_to_render and all_images:
        from reportlab.platypus import Image as RLImage
        
        # Find matching images from the all_images array
        matched_images = []
        for img_id in img_ids_to_render:
            for img_dict in all_images:
                src = img_dict.get("source", "PDF")
                pg = img_dict.get("page", "?")
                idx = img_dict.get("index", "0")
                expected_id = f"{src}_Page{pg}_Index{idx}".replace(" ", "_")
                
                if expected_id == img_id and img_dict.get("image"):
                    matched_images.append((expected_id, img_dict["image"]))
                    break
        
        # Render them in a 2-column grid
        img_table_data = []
        current_row = []
        
        for expected_id, pil_img in matched_images:
            img_buffer = io.BytesIO()
            if pil_img.mode in ('RGBA', 'LA') or (pil_img.mode == 'P' and 'transparency' in pil_img.info):
                pil_img = pil_img.convert('RGB')
            pil_img.save(img_buffer, format="JPEG")
            img_buffer.seek(0)
            
            w, h = pil_img.size
            aspect = h / float(w)
            display_width = 80*mm
            display_height = display_width * aspect
            if display_height > 80*mm:
                display_height = 80*mm
                display_width = display_height / aspect
                
            rl_img = RLImage(img_buffer, width=display_width, height=display_height)
            
            # Label
            label_para = Paragraph(expected_id.replace("_", " "), ParagraphStyle("img_lbl", fontName="Helvetica", fontSize=7, textColor=DARK_GRAY, alignment=TA_CENTER))
            cell_content = [rl_img, Spacer(1, 2*mm), label_para]
            current_row.append(cell_content)
            
            if len(current_row) == 2:
                img_table_data.append(current_row)
                current_row = []
                
        if current_row:
            current_row.append("")  # Pad empty cell
            img_table_data.append(current_row)
            
        if img_table_data:
            img_table = Table(img_table_data, colWidths=[85*mm, 85*mm])
            img_table.setStyle(TableStyle([
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("ALIGN", (0,0), (-1,-1), "CENTER"),
                ("TOPPADDING", (0,0), (-1,-1), 5),
                ("BOTTOMPADDING", (0,0), (-1,-1), 15),
            ]))
            elems.append(Spacer(1, 3*mm))
            elems.append(img_table)

    return elems


# ── Main PDF generation function ──────────────────────────────────────────────
def generate_ddr_pdf(report_text: str, metadata: dict = None, images: list = None) -> bytes:
    """
    Generate a professional UrbanRoof-styled DDR PDF from the report text.

    Args:
        report_text: The full DDR text generated by Gemini.
        metadata: Optional dict with keys:
                  report_date, inspected_by, property_address, report_id,
                  case_no, inspection_date, inspection_time,
                  property_type, floors, year_built, age, prev_audit, prev_repairs
        images: Optional list of dicts with 'image' (PIL Image), 'page', 'source'

    Returns:
        PDF content as bytes.
    """
    if metadata is None:
        metadata = {}

    # Extract metadata from report text if not provided
    def _extract_field(text, label):
        m = re.search(label + r"\s*:?\s*(.+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else "Not Available"

    if not metadata.get("property_address"):
        metadata["property_address"] = _extract_field(report_text, "Prepared For")
    if not metadata.get("inspected_by"):
        metadata["inspected_by"] = _extract_field(report_text, "Inspected By")
    if not metadata.get("report_date"):
        metadata["report_date"] = _extract_field(report_text, "Report Date")
        if metadata["report_date"] == "Not Available":
            metadata["report_date"] = datetime.today().strftime("%B %d, %Y")

    # Build PDF in memory
    buffer = io.BytesIO()
    page_tmpl = DDRPageTemplate(
        property_address=metadata.get("property_address", ""),
        report_id=metadata.get("report_id", "")
    )

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15*mm,
        rightMargin=15*mm,
        topMargin=28*mm,
        bottomMargin=20*mm,
    )

    styles = _build_styles()
    story = []

    # ── Cover Page ──
    _cover_page(story, styles, metadata)

    # ── Disclaimer ──
    _disclaimer_page(story, styles)

    # ── Section 1: Introduction ──
    story.extend(_section_divider(styles, "SECTION 1   INTRODUCTION"))

    sections = _parse_report(report_text)

    s1 = sections.get("s1", "")
    for part_label, part_key in [
        ("1.1 BACKGROUND", "background"),
        ("1.2 OBJECTIVE OF THE HEALTH ASSESSMENT", "objective"),
        ("1.3 SCOPE OF WORK", "scope"),
    ]:
        story.append(Paragraph(part_label, styles["sub_heading"]))
        # Extract subsection text
        m = re.search(r"1\.[123]\s+" + part_label.split()[-1] + r"(.*?)(?=1\.[234]|$)",
                      s1, re.DOTALL | re.IGNORECASE)
        content = m.group(1).strip() if m else s1
        if not content:
            content = "Not Available"
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("-") or line.startswith("•"):
                story.append(Paragraph(line.lstrip("-•").strip(), styles["bullet"],
                                       bulletText="•"))
            else:
                story.append(Paragraph(line, styles["body"]))

    story.append(PageBreak())

    # ── Section 2: General Information ──
    story.extend(_section_divider(styles, "SECTION 2   GENERAL INFORMATION"))
    story.append(Paragraph("2.1 CLIENT & INSPECTION DETAILS", styles["sub_heading"]))

    insp_fields = [
        ("Customer Name / Property:", metadata.get("property_address", "Not Available")),
        ("Case No:", metadata.get("case_no", _extract_field(report_text, "Case No"))),
        ("Date of Inspection:", metadata.get("inspection_date",
                                              _extract_field(report_text, "Date of Inspection"))),
        ("Time of Inspection:", metadata.get("inspection_time",
                                              _extract_field(report_text, "Time of Inspection"))),
        ("Inspected By:", metadata.get("inspected_by", "Not Available")),
    ]
    for label, value in insp_fields:
        story.append(_info_row(label, value, styles))

    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("2.2 DESCRIPTION OF SITE", styles["sub_heading"]))

    site_fields = [
        ("Type of Structure:", metadata.get("property_type",
                                            _extract_field(report_text, "Type of Structure"))),
        ("Number of Floors:", metadata.get("floors",
                                           _extract_field(report_text, "Number of Floors"))),
        ("Year of Construction:", metadata.get("year_built",
                                               _extract_field(report_text, "Year of Construction"))),
        ("Age of Building:", metadata.get("age",
                                          _extract_field(report_text, "Age of Building"))),
        ("Previous Structure Audit Done:", metadata.get("prev_audit",
                                                        _extract_field(report_text, "Previous Structure Audit"))),
        ("Previous Repairs:", metadata.get("prev_repairs",
                                           _extract_field(report_text, "Previous Repairs"))),
    ]
    for label, value in site_fields:
        story.append(_info_row(label, value, styles))

    story.append(PageBreak())

    # ── Section 3: Visual Observations ──
    story.extend(_section_divider(styles, "SECTION 3   VISUAL OBSERVATION AND READINGS"))
    story.append(Paragraph("3.1 SOURCES OF LEAKAGE — SUMMARY", styles["sub_heading"]))

    s2 = sections.get("s2", "")
    for line in s2.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 2*mm))
        elif re.match(r"[A-Z ]+:", line):
            story.append(Paragraph(line, styles["sub_heading"]))
        else:
            story.append(Paragraph(line, styles["body"]))

    story.append(Spacer(1, 4*mm))

    # Area-wise observations
    s3 = sections.get("s3", "")
    areas = _parse_areas(s3)
    if areas:
        story.append(Paragraph("3.2 AREA-WISE DETAILED OBSERVATIONS", styles["sub_heading"]))
        for i, area in enumerate(areas, 1):
            for elem in _area_block(area, styles, i, all_images=images):
                story.append(elem)
            story.append(Spacer(1, 5*mm))
    else:
        # Fallback: render s3 as plain text
        for line in s3.split("\n"):
            if line.strip():
                story.append(Paragraph(line.strip(), styles["body"]))

    story.append(PageBreak())

    # ── Section 4: Structural Assessments ──
    story.extend(_section_divider(styles, "SECTION 4   STRUCTURAL CONDITION ASSESSMENTS"))
    s4 = sections.get("s4", "")

    # Try to render sub-sections
    for sub_title, sub_key in [
        ("4.1 TERRACE CONDITION ASSESSMENT", "TERRACE"),
        ("4.2 RCC MEMBERS CONDITION", "RCC"),
        ("4.3 EXTERIOR WALL CONDITION", "EXTERIOR WALL"),
    ]:
        m = re.search(sub_key + r"(.*?)(?=4\.[234]|$)", s4, re.DOTALL | re.IGNORECASE)
        content = m.group(1).strip() if m else ""
        if not content or "not available" in content.lower():
            continue
        story.append(Paragraph(sub_title, styles["sub_heading"]))
        # Try to parse numbered items: "1. Description: rating - remarks"
        rows = []
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Match: "1. Label: rating - remarks"
            num_m = re.match(r"\d+\.\s*(.+?):\s*(.+?)(?:\s*-\s*(.*))?$", line)
            if num_m:
                desc    = num_m.group(1).strip()
                rating  = num_m.group(2).strip().lower()
                remarks = num_m.group(3).strip() if num_m.group(3) else ""
                rows.append(f"{desc} | {rating} | {remarks}")
            else:
                story.append(Paragraph(line, styles["body"]))
        if rows:
            story.append(_condition_table(rows, styles))
        story.append(Spacer(1, 3*mm))

    if not s4.strip():
        story.append(Paragraph("Structural condition assessment data not available in provided documents.",
                               styles["body"]))

    story.append(PageBreak())

    # ── Section 5: Analysis & Suggestions ──
    story.extend(_section_divider(styles, "SECTION 5   ANALYSIS & SUGGESTIONS"))
    s5 = sections.get("s5", "")

    therapy_labels = [
        ("5.1 BATHROOM AND BALCONY GROUTING TREATMENT", "BATHROOM"),
        ("5.2 PLUMBING", "PLUMBING"),
        ("5.3 TERRACE WATERPROOFING TREATMENT", "TERRACE WATERPROOF"),
        ("5.4 EXTERNAL WALL TREATMENT", "EXTERNAL WALL"),
        ("5.5 PLASTER WORK", "PLASTER"),
        ("5.6 RCC MEMBERS TREATMENT", "RCC"),
    ]
    any_found = False
    for label, key in therapy_labels:
        m = re.search(key + r"(.*?)(?=5\.[123456]|$)", s5, re.DOTALL | re.IGNORECASE)
        content = m.group(1).strip() if m else ""
        if not content or "not applicable" in content.lower() or len(content) < 10:
            continue
        any_found = True
        story.append(Paragraph(label, styles["sub_heading"]))
        for para in content.split("\n\n"):
            para = para.strip()
            if para:
                story.append(Paragraph(para, styles["body"]))
        story.append(Spacer(1, 3*mm))

    if not any_found:
        # Render s5 as-is
        for line in s5.split("\n"):
            if line.strip():
                story.append(Paragraph(line.strip(), styles["body"]))

    story.append(PageBreak())

    # ── Section 6: Severity & Summary ──
    story.extend(_section_divider(styles, "SECTION 6   SUMMARY TABLE AND ACTIONS"))
    s6 = sections.get("s6", "")

    # Overall severity
    sev_m = re.search(r"OVERALL SEVERITY\s*:?\s*(\w+)", s6, re.IGNORECASE)
    severity = sev_m.group(1).strip() if sev_m else "Not Available"
    sev_style = (styles["severity_high"] if "high" in severity.lower()
                 else styles["severity_mod"] if "moderate" in severity.lower()
                 else styles["severity_low"] if "low" in severity.lower()
                 else styles["body"])
    story.append(Paragraph(f"Overall Severity: {severity}", sev_style))
    story.append(Spacer(1, 4*mm))

    # Summary table
    pairs = []
    table_m = re.search(r"SUMMARY OF IMPACTED(.*?)PRIORITY ACTIONS", s6, re.DOTALL | re.IGNORECASE)
    if table_m:
        rows_text = table_m.group(1).strip()
        for line in rows_text.split("\n"):
            if "|" in line and "Impacted" not in line and "---" not in line:
                parts = [p.strip() for p in line.split("|") if p.strip()]
                if len(parts) >= 2:
                    neg = parts[1] if len(parts) > 1 else parts[0]
                    pos = parts[3] if len(parts) > 3 else (parts[2] if len(parts) > 2 else "")
                    if neg:
                        pairs.append((neg, pos))

    if pairs:
        story.append(Paragraph("Summary of Impacted Areas vs Exposed Sources", styles["sub_heading"]))
        story.append(_summary_table(pairs, styles))
        story.append(Spacer(1, 4*mm))

    # Priority actions
    for priority_label in ["IMMEDIATE", "SHORT-TERM", "LONG-TERM"]:
        m = re.search(priority_label + r"[^:]*:(.*?)(?=IMMEDIATE|SHORT-TERM|LONG-TERM|$)",
                      s6, re.DOTALL | re.IGNORECASE)
        if m:
            content = m.group(1).strip()
            if content and len(content) > 5:
                label_map = {
                    "IMMEDIATE": "IMMEDIATE — Address within 1-2 weeks",
                    "SHORT-TERM": "SHORT-TERM — Address within 1-3 months",
                    "LONG-TERM": "LONG-TERM — Address within 3-6 months",
                }
                story.append(Paragraph(label_map[priority_label], styles["sub_heading"]))
                for line in content.split("\n"):
                    line = line.strip().lstrip("-•").strip()
                    if line:
                        story.append(Paragraph(line, styles["bullet"], bulletText="•"))
                story.append(Spacer(1, 2*mm))

    story.append(PageBreak())

    # ── Section 7: Notes & Missing Info ──
    story.extend(_section_divider(styles, "SECTION 7   LIMITATION AND PRECAUTION NOTE"))
    s7 = sections.get("s7", "")

    for sub in ["7.1 ADDITIONAL OBSERVATIONS", "7.2 MISSING OR UNCLEAR INFORMATION"]:
        story.append(Paragraph(sub, styles["sub_heading"]))
        key = "ADDITIONAL" if "7.1" in sub else "MISSING"
        m = re.search(key + r"(.*?)(?=7\.[12]|$)", s7, re.DOTALL | re.IGNORECASE)
        content = m.group(1).strip() if m else ""
        if not content:
            content = "None" if key == "MISSING" else "Not Available"
        for line in content.split("\n"):
            line = line.strip()
            if line:
                story.append(Paragraph(line, styles["body"]))
    # ── Extracted Images Section (Removed since images are now inline) ──
    # The dedicated images section at the end is removed because
    # images are mapped correctly inline using Gemini Vision markers.

    # Legal disclaimer
    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=MID_GRAY))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Legal Disclaimer", styles["sub_heading"]))
    story.append(Paragraph(
        "UrbanRoof has performed a visual and non-destructive test inspection of the property/structure "
        "and provides the CLIENT with an inspection report giving an opinion of the present condition of "
        "the property. The Inspector's Report is an opinion of the present condition of the property "
        "based on a visual examination of the readily accessible features of the property. "
        "UrbanRoof is not responsible for any incorrect information supplied to us by client, customer, or users. "
        "This report is subject to copyrights held with UrbanRoof Private Limited.",
        styles["disclaimer"]
    ))

    # Build PDF
    def _on_page(canvas, doc):
        page_tmpl.on_page(canvas, doc)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def save_ddr_pdf(report_text: str, output_path: str, metadata: dict = None) -> str:
    """Save DDR as PDF to the given path. Returns the path."""
    pdf_bytes = generate_ddr_pdf(report_text, metadata)
    with open(output_path, "wb") as f:
        f.write(pdf_bytes)
    return output_path
