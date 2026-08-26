from core.pdf_io import (
    read_pdf,
    write_pdf,
    _reconstruct_columned_table,
    _find_header_words,
    _is_degenerate_table,
    _PAGE_BREAK,
)
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


def test_transaction_line_is_not_mistaken_for_the_header_row():
    # OCR (or a mangled font) can garble the real header's date-label word past
    # recognition, while an ordinary transaction line coincidentally contains
    # both keywords — e.g. a "Wert:" value-date annotation and a "Gutschrift"
    # (credit) description — and, crucially, starts with the row's own real
    # date. A real column header is never itself a dated transaction line, so
    # that shape must not be mistaken for one, even when no better candidate
    # exists — a wrong header corrupts every row bucketed under it.
    transaction_line = [
        _word("07.01.2025|Gutschrift", 0, 90, 100),
        _word("Uberw.", 95, 130, 100),
        _word("Wert:", 135, 165, 100),
        _word("06.01.2025", 170, 220, 100),
    ]
    lines = [transaction_line]

    assert _find_header_words(lines) is None


def test_short_two_word_fragment_is_not_mistaken_for_the_header_row():
    # A second false-positive shape seen in real OCR output: a wrapped
    # continuation fragment of a transaction line ("Gutschrift / Wert:
    # 06.01.2025" — the tail end of a credit description plus its value-date
    # note) that doesn't start with a date, so the date-anchor guard above
    # doesn't catch it, but still coincidentally contains both header
    # keywords. A real column header always has several separately-clustered
    # column labels (Date, Description, Amount, ...); this fragment clusters
    # into only two words' worth of groups and must be rejected on that basis.
    fragment_line = [
        _word("Gutschrift", 138, 179, 581),
        _word("/", 213, 215, 581),
        _word("Wert:", 218, 240, 581),
        _word("06.01.2025", 243, 290, 581),
    ]
    lines = [fragment_line]

    assert _find_header_words(lines) is None


def test_both_present_amount_pair_is_not_mistaken_for_a_debit_credit_split():
    # Real-world shape ("Originalumsatz" / "EUR-Umsatz" on a Sparkasse-style
    # export): both columns carry a value on every row, restating the same
    # figure in two forms — but only the first repeats the currency code next
    # to the number ("2.373,80H EUR"); the second is a bare number with no
    # adjacent currency ("2.373,80H"). A whole-row currency-tagged amount scan
    # only ever counts the first, making this look identical to a genuine
    # debit/credit split (exactly one of two columns populated) even though
    # both are actually meant to be present on every row — misrouting the bare
    # second value would silently blank out a real column on every row.
    header = [
        _word("Datum", 0, 40, 0),
        _word("Originalumsatz", 320, 400, 0),
        _word("EUR-Umsatz", 420, 480, 0),
    ]
    row1 = [
        _word("02.01.2024", 0, 40, 100),
        _word("2.373,80H", 320, 360, 100),
        _word("EUR", 365, 385, 100),
        _word("2.373,80H", 420, 460, 100),
    ]
    row2 = [
        _word("03.01.2024", 0, 40, 120),
        _word("1.037,80H", 320, 360, 120),
        _word("EUR", 365, 385, 120),
        _word("1.037,80H", 420, 460, 120),
    ]
    lines = [header, row1, row2]

    table, _preamble = _reconstruct_columned_table(lines)

    assert table, "expected the column reconstruction to succeed"
    orig_col = table[0].index("Originalumsatz")
    eur_col = table[0].index("EUR-Umsatz")
    assert table[1][orig_col] == "2.373,80"
    assert table[1][eur_col] == "2.373,80"
    assert table[2][orig_col] == "1.037,80"
    assert table[2][eur_col] == "1.037,80"


def test_table_with_a_near_empty_column_is_degenerate():
    # pdfplumber's own table detector occasionally imagines a faint grid in
    # ordinary borderless text (e.g. a page whose wrapped lines happen to align
    # into two loose "columns") and reports it as a real 2-column table — but a
    # real document shows its second column populated on barely any row (3-11%,
    # a coincidental alignment on a stray line or two), never blank on literally
    # every single one. Treating that as real interrupts a long borderless
    # statement's continuous reconstruction — flushing whatever was accumulated
    # so far and restarting from scratch — fragmenting one document into dozens
    # of disjointed pieces. A genuine multi-column table is populated far more
    # consistently than that in every column.
    extracted = [
        ["20.02.2024", ""],
        ["154352990-2764324-MOESSNER RG.", ""],
        ["WM GRUNDSTUECKSVERW. GMBH", ""],
        ["70558,OP.1294881,202", ""],
        ["163 2761", "stray"],
        ["WM GRUNDSTUECKSVERW. GMBH", ""],
        ["102103727-2769725-IU MOESSER", ""],
        ["72244,OP.1297288,F124726", ""],
    ]

    assert _is_degenerate_table(extracted)


def test_page_footer_glued_onto_open_row_does_not_override_its_real_date():
    # Real-world shape (Qonto statements): a repeated page footer restating the
    # whole statement's own date range ("Vom 01/03/2025 bis zum 31/03/2025")
    # sits at the bottom of every page, after the last transaction — so it gets
    # appended to whatever row is still open when the page ends, rather than
    # recognized as furniture. The row's own date is a slash date with no year
    # ("28/03"), resolved via the statement's inferred year; the footer's date
    # is a *full* slash date. A plain date-scan over the row's whole
    # accumulated text finds the footer's full date first (it's tried before
    # the no-year fallback) and wrongly reports the statement's start date
    # instead of the row's own.
    header = [
        _word("Datum", 0, 40, 0),
        _word("Transaktionen", 60, 200, 0),
        _word("Betrag", 300, 360, 0),
    ]
    preamble = [_word("Vom", 0, 20, 5), _word("01/03/2025", 25, 80, 5),
                _word("bis", 85, 100, 5), _word("zum", 105, 125, 5),
                _word("31/03/2025", 130, 185, 5)]
    row1 = [
        _word("28/03", 0, 30, 100),
        _word("Payee", 60, 100, 100),
        _word("999,00", 300, 340, 100),
    ]
    footer = [_word("Vom", 0, 20, 200), _word("01/03/2025", 25, 80, 200),
              _word("bis", 85, 100, 200), _word("zum", 105, 125, 200),
              _word("31/03/2025", 130, 185, 200)]
    row2 = [
        _word("29/03", 0, 30, 300),
        _word("Other", 60, 100, 300),
        _word("500,00", 300, 340, 300),
    ]
    lines = [preamble, header, row1, footer, _PAGE_BREAK, row2]

    table, _preamble = _reconstruct_columned_table(lines)

    assert table, "expected the column reconstruction to succeed"
    date_col = table[0].index("Datum")
    assert table[1][date_col] == "28/03/2025"


def test_date_glued_directly_onto_the_next_words_description_is_not_lost():
    # Real-world shape (a Sparkasse statement): some exports glue the row's
    # date straight onto the first word of its own description with no space
    # ("29.12.2023Entgeltabrechnung") — a single pdfplumber token. Bucketing
    # by x-position puts that whole token in the date column since it starts
    # there, and _normalize_date only pulls the date portion back out for the
    # date column's own value — the glued description word was never routed
    # anywhere else, silently vanishing from the row instead of landing in
    # the description column with the rest of that line's words.
    header = [
        _word("Datum", 0, 40, 0),
        _word("Erlaeuterung", 60, 200, 0),
        _word("Betrag", 300, 360, 0),
    ]
    row1 = [
        _word("29.12.2023Entgeltabrechnung", 0, 100, 100),
        _word("/", 105, 110, 100),
        _word("Wert:", 115, 140, 100),
        _word("30.12.2023", 145, 195, 100),
        _word("-9,50", 300, 340, 100),
    ]
    row2 = [
        _word("30.12.2023", 0, 40, 120),
        _word("Rechnung", 60, 100, 120),
        _word("-3,00", 300, 340, 120),
    ]
    lines = [header, row1, row2]

    table, _preamble = _reconstruct_columned_table(lines)

    assert table, "expected the column reconstruction to succeed"
    date_col = table[0].index("Datum")
    desc_col = table[0].index("Erlaeuterung")
    assert table[1][date_col] == "29.12.2023"
    assert "Entgeltabrechnung" in table[1][desc_col]


def test_first_rows_own_tall_cell_starting_above_its_date_is_not_dropped():
    # Real-world shape (a bordered-grid statement whose first transaction has a
    # multi-line description): the description cell renders starting a little
    # above the row's own date/amount baseline, so its first physical line
    # sorts ahead of the row-start line by vertical position and is seen here
    # before any row has started yet ("current is None"). Since it carries no
    # amount of its own, it isn't a standalone summary/total line (those
    # always show one) — it's the first row's own leading content and must
    # land in that row, not be discarded as document preamble.
    header = [
        _word("Datum", 0, 40, 0),
        _word("Verwendungszweck", 60, 300, 0),
        _word("Betrag", 400, 460, 0),
    ]
    orphan_first_line = [_word("ERSTATT.027/062/01218", 60, 200, 90)]
    row1 = [
        _word("15.07.2026", 0, 60, 100),
        _word("GEW.ST", 60, 100, 100),
        _word("2023", 105, 130, 100),
        _word("96.948,85", 400, 450, 100),
    ]
    row2 = [
        _word("16.07.2026", 0, 60, 120),
        _word("Sonstiges", 60, 120, 120),
        _word("12,00", 400, 450, 120),
    ]
    lines = [header, orphan_first_line, row1, row2]

    table, preamble = _reconstruct_columned_table(lines)

    assert table, "expected the column reconstruction to succeed"
    desc_col = table[0].index("Verwendungszweck")
    assert "ERSTATT.027/062/01218" in table[1][desc_col]
    assert not preamble


def test_opening_balance_line_before_first_row_is_not_merged_into_it():
    # A real standalone summary line ("Kontostand am 30.11.2023, Auszug Nr.
    # 11    10.518,94") sits between the header and the first transaction, and
    # — unlike the orphan-content case above — genuinely does not belong to
    # that first row. Its amount has no currency code of its own (the column
    # header already states "Betrag EUR" once), so a currency-tagged scan of
    # the line wrongly sees "no amount" and would let it be merged into row 1
    # — corrupting row 1's own real amount with the balance figure instead.
    # The amount check must find it directly in its own amount-column bucket.
    header = [
        _word("Datum", 0, 40, 0),
        _word("Erlaeuterung", 60, 200, 0),
        _word("Betrag", 300, 360, 0),
    ]
    balance_line = [
        _word("Kontostand", 60, 120, 90),
        _word("am", 125, 140, 90),
        _word("30.11.2023,", 145, 200, 90),
        _word("Auszug", 205, 240, 90),
        _word("Nr.", 245, 260, 90),
        _word("11", 265, 280, 90),
        _word("10.518,94", 300, 350, 90),
    ]
    row1 = [
        _word("05.12.2023", 0, 60, 100),
        _word("Dauerauftrag", 60, 130, 100),
        _word("-500,00", 300, 350, 100),
    ]
    row2 = [
        _word("12.12.2023", 0, 60, 120),
        _word("Gutschrift", 60, 120, 120),
        _word("693,00", 300, 350, 120),
    ]
    lines = [header, balance_line, row1, row2]

    table, preamble = _reconstruct_columned_table(lines)

    assert table, "expected the column reconstruction to succeed"
    betrag_col = table[0].index("Betrag")
    desc_col = table[0].index("Erlaeuterung")
    assert table[1][betrag_col] == "-500,00"
    assert "Kontostand" not in table[1][desc_col]
    assert preamble and "Kontostand" in preamble
