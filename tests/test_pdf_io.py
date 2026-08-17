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


def test_special_characters_survive_round_trip(tmp_path):
    p = tmp_path / "special.pdf"
    text = "R&D grew, <50% margin, cost>revenue"
    blocks = [("text", text)]

    write_pdf(blocks, str(p))
    result = read_pdf(str(p))

    joined = " ".join(c for k, c in result if k == "text")
    assert "R&D" in joined
    assert "<50%" in joined
    assert "cost>revenue" in joined


def test_table_content_not_duplicated_in_text_block(tmp_path):
    p = tmp_path / "mixed.pdf"
    blocks = [
        ("text", "Intro line before table"),
        ("table", [["Name", "Age"], ["Bob", "30"]]),
        ("text", "Outro line after table"),
    ]

    write_pdf(blocks, str(p))
    result = read_pdf(str(p))

    tables = [c for k, c in result if k == "table"]
    texts = [c for k, c in result if k == "text"]
    assert tables and tables[0] == [["Name", "Age"], ["Bob", "30"]]
    joined_text = " ".join(texts)
    assert "Bob" not in joined_text
    assert "30" not in joined_text
    assert "Intro line before table" in joined_text
    assert "Outro line after table" in joined_text


def test_wide_table_does_not_raise_and_produces_file(tmp_path):
    p = tmp_path / "wide.pdf"
    num_cols = 15
    header = [f"Col{i}" for i in range(num_cols)]
    row = [str(i) for i in range(num_cols)]
    blocks = [("table", [header, row])]

    write_pdf(blocks, str(p))

    assert p.exists()
    assert p.stat().st_size > 0
    # Should still be readable back without error, confirming the table wasn't
    # silently mangled by being squeezed/forced off the page.
    result = read_pdf(str(p))
    tables = [c for k, c in result if k == "table"]
    assert tables
    # Narrow columns can force pdfplumber to read a wrapped cell back with an
    # internal newline (e.g. "Col0" -> "Col\n0"); strip those before comparing.
    normalized = [cell.replace("\n", "") for cell in tables[0][0]]
    assert normalized == header
