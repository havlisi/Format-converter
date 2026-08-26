from core.pdf_io import read_pdf, write_pdf, _reconstruct_columned_table
import pytest


def _word(text, x0, x1, top, bottom=None):
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": bottom or top + 10}


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


def test_reconstructs_borderless_financial_statement(tmp_path):
    p = tmp_path / "stmt.pdf"
    # Synthetic bank-statement text: date + payee + amount + running balance per
    # transaction, no ruling lines — the shape pdfplumber's own table detector fails
    # on for real statements. "RE.500,00" mimics an invoice reference that looks
    # like a second amount but has no currency code after it, so it must be ignored.
    lines = [
        "Kontoauszug Testbank",
        "01.01.2024 Acme Corp Miete Januar 1.000,00 EUR 5.000,00 EUR",
        "166 continuation code line",
        "02.01.2024 Beta LLC RE.500,00 Nebenkosten -200,00 EUR 4.800,00 EUR",
        "ref continuation IBAN DE89370400440532013000",
    ]
    write_pdf([("text", "\n".join(lines))], str(p))
    result = read_pdf(str(p))

    tables = [c for k, c in result if k == "table"]
    assert tables, "expected the borderless statement to be reconstructed as a table"
    table = tables[0]
    assert table[0][0] == "Date"
    rows = table[1:]
    assert len(rows) == 2
    assert rows[0][0] == "01.01.2024"
    assert rows[0][1] == "1.000,00"
    assert rows[0][2] == "5.000,00"
    assert rows[1][0] == "02.01.2024"
    assert rows[1][1] == "-200,00"
    assert rows[1][2] == "4.800,00"  # not the "RE.500,00" reference number
    assert "DE89370400440532013000" in rows[1][3]


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


def test_single_amount_column_ignores_amount_embedded_in_description():
    # Real-world shape (a German bank statement's "Verwendungszweck" free-text
    # column): the description names an unrelated, currency-tagged amount
    # ("40,00 EUR", a reference cited in the narrative) positioned to the LEFT
    # of the row's actual "Betrag" column, on the same physical line. The real
    # transaction amount, "999,00", sits in its own bucket further right with
    # no currency word glued next to it (the currency has its own column, as
    # real statements often do). A row-wide left-to-right amount scan picks
    # whichever amount appears first in reading order — the narrative one, not
    # the real one — corrupting the figure that must never be misattributed.
    header = [
        _word("Datum", 0, 40, 0),
        _word("Verwendungszweck", 60, 200, 0),
        _word("Betrag", 320, 380, 0),
    ]
    row1 = [
        _word("01.03.2024", 0, 40, 100),
        _word("Rechnung", 60, 100, 100),
        _word("40,00", 105, 130, 100),
        _word("EUR", 135, 155, 100),
        _word("Nachzahlung", 160, 220, 100),
        _word("999,00", 320, 360, 100),
    ]
    row2 = [
        _word("02.03.2024", 0, 40, 120),
        _word("Miete", 60, 100, 120),
        _word("500,00", 320, 360, 120),
    ]
    lines = [header, row1, row2]

    table, _preamble = _reconstruct_columned_table(lines)

    assert table, "expected the column reconstruction to succeed"
    betrag_col = table[0].index("Betrag")
    assert table[1][betrag_col] == "999,00"
    assert table[2][betrag_col] == "500,00"
