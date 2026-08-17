import pdfplumber
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from core.types import Block
from typing import List


def _bbox_overlaps(obj: dict, bbox: tuple) -> bool:
    """True if a pdfplumber char/word object overlaps a (x0, top, x1, bottom) bbox."""
    bx0, btop, bx1, bbottom = bbox
    ox0, otop, ox1, obottom = obj["x0"], obj["top"], obj["x1"], obj["bottom"]
    return not (ox1 <= bx0 or ox0 >= bx1 or obottom <= btop or otop >= bbottom)


def read_pdf(path: str) -> List[Block]:
    blocks: List[Block] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            found_tables = page.find_tables()
            for table in found_tables:
                extracted = table.extract()
                cleaned = [["" if cell is None else cell for cell in row] for row in extracted]
                blocks.append(("table", cleaned))

            if found_tables:
                table_bboxes = [t.bbox for t in found_tables]
                text_page = page.filter(
                    lambda obj: not any(_bbox_overlaps(obj, bbox) for bbox in table_bboxes)
                )
                text = text_page.extract_text()
            else:
                text = page.extract_text()

            if text:
                blocks.append(("text", text))
    if not blocks:
        raise ValueError("no extractable text — likely scanned image, OCR not supported")
    return blocks


def write_pdf(blocks: List[Block], path: str) -> None:
    doc = SimpleDocTemplate(path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    for kind, content in blocks:
        if kind == "text":
            for line in content.split("\n"):
                if line.strip():
                    story.append(Paragraph(escape(line), styles["Normal"]))
            story.append(Spacer(1, 12))
        else:
            num_cols = max((len(row) for row in content), default=1) or 1
            col_width = doc.width / num_cols
            wrapped = [
                [Paragraph(escape(str(cell)), styles["Normal"]) for cell in row]
                for row in content
            ]
            table = Table(wrapped, colWidths=[col_width] * num_cols)
            table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ]))
            story.append(table)
            story.append(Spacer(1, 12))
    if not story:
        story.append(Paragraph(" ", styles["Normal"]))
    doc.build(story)
