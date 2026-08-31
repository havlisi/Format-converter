import os
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from core import docx_io
from core.docx_io import read_docx, write_docx


def _make_text_pdf(path):
    doc = SimpleDocTemplate(path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Kontoauszug Nr. 7", styles["Title"]),
        Paragraph("Kontoinhaber: Musterfirma GmbH", styles["Normal"]),
        Spacer(1, 12),
        Table([["Datum", "Betrag"], ["01.03.2026", "1.234,56"], ["02.03.2026", "-99,00"]]),
    ]
    doc.build(story)


def test_pdf_to_docx_preserves_text_and_table(tmp_path):
    pdf = str(tmp_path / "src.pdf")
    out = str(tmp_path / "src.docx")
    _make_text_pdf(pdf)

    docx_io.pdf_to_docx(pdf, out)

    assert os.path.exists(out)
    doc = Document(out)
    all_text = "\n".join(p.text for p in doc.paragraphs)
    all_text += "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert "Kontoinhaber: Musterfirma GmbH" in all_text
    assert "1.234,56" in all_text
    assert "02.03.2026" in all_text


def test_pdf_to_docx_scanned_falls_back_to_block_pipeline(tmp_path, monkeypatch):
    pdf = str(tmp_path / "scan.pdf")
    out = str(tmp_path / "scan.docx")
    # content doesn't matter — we force the "no text layer" branch
    open(pdf, "wb").write(b"%PDF-1.4\n%%EOF\n")

    monkeypatch.setattr(docx_io, "_pdf_has_text_layer", lambda p: False)
    sentinel = [("text", "OCR line one"), ("table", [["a", "b"]])]
    monkeypatch.setattr("core.pdf_io.read_pdf", lambda p: sentinel)

    called = {}
    real_write = docx_io.write_docx

    def spy_write(blocks, path):
        called["blocks"] = blocks
        real_write(blocks, path)

    monkeypatch.setattr(docx_io, "write_docx", spy_write)

    docx_io.pdf_to_docx(pdf, out)

    assert called["blocks"] == sentinel
    assert os.path.exists(out)


def test_write_then_read_text_block(tmp_path):
    p = tmp_path / "out.docx"
    blocks = [("text", "Hello world")]

    write_docx(blocks, str(p))
    result = read_docx(str(p))

    assert result == [("text", "Hello world")]


def test_write_then_read_table_block(tmp_path):
    p = tmp_path / "out2.docx"
    blocks = [("table", [["Name", "Age"], ["Bob", "30"]])]

    write_docx(blocks, str(p))
    result = read_docx(str(p))

    assert result == [("table", [["Name", "Age"], ["Bob", "30"]])]


def test_order_preserved_text_then_table(tmp_path):
    p = tmp_path / "out3.docx"
    blocks = [("text", "Intro"), ("table", [["x", "y"]])]

    write_docx(blocks, str(p))
    result = read_docx(str(p))

    assert result == [("text", "Intro"), ("table", [["x", "y"]])]
