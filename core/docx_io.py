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
