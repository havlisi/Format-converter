import pdfplumber
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from core.types import Block
from typing import List


def read_pdf(path: str) -> List[Block]:
    blocks: List[Block] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                cleaned = [["" if cell is None else cell for cell in row] for row in table]
                blocks.append(("table", cleaned))
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
                    story.append(Paragraph(line, styles["Normal"]))
            story.append(Spacer(1, 12))
        else:
            table = Table(content)
            table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
            ]))
            story.append(table)
            story.append(Spacer(1, 12))
    if not story:
        story.append(Paragraph(" ", styles["Normal"]))
    doc.build(story)
