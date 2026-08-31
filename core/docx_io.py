from docx import Document
from docx.text.paragraph import Paragraph
from docx.table import Table
from core.types import Block
from typing import List


def read_docx(path: str) -> List[Block]:
    doc = Document(path)
    blocks: List[Block] = []
    for element in doc.element.body.iterchildren():
        if element.tag.endswith("}p"):
            para = Paragraph(element, doc)
            if para.text.strip():
                blocks.append(("text", para.text))
        elif element.tag.endswith("}tbl"):
            table = Table(element, doc)
            rows = [[cell.text for cell in row.cells] for row in table.rows]
            blocks.append(("table", rows))
    return blocks


def write_docx(blocks: List[Block], path: str) -> None:
    doc = Document()
    for kind, content in blocks:
        if kind == "text":
            doc.add_paragraph(content)
        else:
            if not content:
                continue
            n_rows = len(content)
            n_cols = max(len(r) for r in content)
            table = doc.add_table(rows=n_rows, cols=n_cols)
            table.style = "Table Grid"
            for r_idx, row in enumerate(content):
                for c_idx in range(n_cols):
                    val = row[c_idx] if c_idx < len(row) else ""
                    table.cell(r_idx, c_idx).text = "" if val is None else str(val)
    doc.save(path)


def _pdf_has_text_layer(pdf_path: str) -> bool:
    """True if any page yields extractable words. A scanned/image-only PDF
    returns False and is routed through OCR instead of pdf2docx."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            if page.extract_words():
                return True
    return False


def pdf_to_docx(pdf_path: str, docx_path: str) -> None:
    """Convert a PDF to DOCX preserving page layout via pdf2docx. A scanned PDF
    with no text layer has no layout to preserve — route it through the existing
    OCR block pipeline so the DOCX at least carries searchable text."""
    if not _pdf_has_text_layer(pdf_path):
        from core import pdf_io
        write_docx(pdf_io.read_pdf(pdf_path), docx_path)
        return

    import logging

    from pdf2docx import Converter

    logging.getLogger("pdf2docx").setLevel(logging.WARNING)

    cv = Converter(pdf_path)
    try:
        cv.convert(docx_path)
    finally:
        cv.close()
