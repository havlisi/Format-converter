from core.pdf_io import read_pdf, write_pdf
import pytest


def test_write_then_read_text_only(tmp_path):
    p = tmp_path / "out.pdf"
    blocks = [("text", "Hello world from converter")]

    write_pdf(blocks, str(p))
    result = read_pdf(str(p))

    joined = " ".join(c for k, c in result if k == "text")
    assert "Hello world from converter" in joined


def test_write_then_read_table(tmp_path):
    p = tmp_path / "out2.pdf"
    blocks = [("table", [["Name", "Age"], ["Bob", "30"]])]

    write_pdf(blocks, str(p))
    result = read_pdf(str(p))

    tables = [c for k, c in result if k == "table"]
    assert tables, "expected at least one table block"
    assert tables[0] == [["Name", "Age"], ["Bob", "30"]]


def test_read_raises_on_no_text(tmp_path):
    p = tmp_path / "blank.pdf"
    write_pdf([], str(p))

    with pytest.raises(ValueError, match="no extractable text"):
        read_pdf(str(p))
