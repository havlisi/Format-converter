import re
import pdfplumber
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from core.types import Block
from typing import List, Optional, Tuple

# Two decimal conventions, both seen in real statements: European (thousands with
# dots, decimal comma — "1.234,56") and international (thousands with commas,
# decimal point — "1,234.56"), each with a plain ungrouped form too (some exports
# skip thousands separators — "17159.30"). Grouped forms require *at least one*
# separator group (`+`, not `*`) and are tried before the plain fallbacks — without
# that, "1,000.00" would match the EU-shaped prefix "1,00" first and silently drop
# "0.00", since a 0-group EU pattern is happy to treat any leading digit + comma +
# 2 digits as a complete (wrong) match.
#
# `(?<!\d)` (not preceded by a digit), rather than `\b`, guards where a match may
# start. It blocks starting mid-digit-run (so an ungrouped number can't match
# partway through, e.g. "159.30" out of "17159.30") while still allowing a match to
# start right after a *letter* glued directly onto the number with no space (e.g. a
# reference-code prefix in "A1.125,00 EUR") — `\b` would wrongly block that position
# too (letter-to-digit is a word-internal, not a boundary), forcing the match to
# start after the number's own thousands-separator dot instead and returning a
# truncated "125,00".
_AMOUNT_EU_GROUPED = r"\d{1,3}(?:\.\d{3})+,\d{2}"
_AMOUNT_INTL_GROUPED = r"\d{1,3}(?:,\d{3})+\.\d{2}"
_AMOUNT_EU_PLAIN = r"\d+,\d{2}"
_AMOUNT_INTL_PLAIN = r"\d+\.\d{2}"
_AMOUNT_NUM = (
    r"(?<!\d)"
    rf"(?:{_AMOUNT_EU_GROUPED}|{_AMOUNT_INTL_GROUPED}|{_AMOUNT_EU_PLAIN}|{_AMOUNT_INTL_PLAIN})"
)

# Anchors a line as a financial transaction row: an amount immediately next to a
# currency code (e.g. "1.234,56 EUR", "-12,34EUR", "+ 17159.30 EUR"), optionally
# with a leading +/- (glued or with a space) and/or a trailing German Haben/Soll
# debit-credit marker (e.g. "2.373,80H EUR" credit, "138,19 S EUR" debit — some
# banks encode the sign as this letter, glued or space-separated, instead of a
# leading minus). Requiring the currency suffix is what tells a real amount apart
# from a same-shaped number elsewhere in the line — e.g. an invoice reference like
# "RE.476,29" that would otherwise be mistaken for a second amount and shift every
# column after it.
_AMOUNT_RE = re.compile(rf"([+-]\s?)?({_AMOUNT_NUM})\s?([HS])?\s*(?:EUR|USD|GBP|CHF|RSD)\b")
_DATE_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")
# IBANs appear either compact ("DE76550104001041824990") or human-readable with a
# space every 4 characters ("DE75 1203 0000 0001 2987 77") — both must match. The
# spaced groups are restricted to digits: letting them match letters too would let
# the match run on into the next actual word (e.g. a payee name right after it).
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[A-Z0-9]{10,30}|(?:\s\d{2,4}){2,8})\b")

# A decimal amount with no currency requirement — only used once a word has already
# been confined to a column whose own header says it's an amount field (see the
# column-position reconstruction below), so the currency check that _AMOUNT_RE needs
# for safety in free text isn't necessary here.
_BARE_AMOUNT_RE = re.compile(rf"([+-]\s?)?({_AMOUNT_NUM})\s?([HS])?")
# A date whose year wrapped onto the next physical line in a narrow column
# ("03.01." then "2022" below it) — matched once both fragments are gathered into
# the same header-derived date column.
_SPLIT_DATE_RE = re.compile(r"(\d{1,2}\.\d{1,2}\.)\s*(\d{4})")
# Marks the start of a new row within a header-derived date column: the bucket must
# *begin* with a (possibly partial, for a year wrapped onto the next line) date.
# Trailing content is allowed — some exports glue the date straight onto the next
# word with no space ("05.12.2023Dauerauftrag") — except when what follows looks
# like a clock time ("21.02.2025 11:43:30"), which marks a page's printed
# generation timestamp rather than a transaction date; matching that would spawn a
# bogus row swallowing the repeated document preamble around it.
#
# The year is matched as an explicit either/or, not `(?:\d{4})?` — a plain optional
# group would let the engine dodge the "not followed by a time" check by simply
# backtracking to *not* consume the year, re-running the lookahead one position
# earlier where the time no longer immediately follows, and matching anyway.
# Forcing a choice between "there's a 4-digit year here, and no time after it" and
# "there's no 4-digit year here at all" closes that loophole.
_ROW_START_DATE_RE = re.compile(r"^\d{1,2}\.\d{1,2}\.(?:\d{4}(?!\s*\d{1,2}:\d{2})|(?!\d{4}))")

# Column-header keyword matches (case-insensitive, matched as a substring so
# abbreviated headers like "Werts.." or "Umsatz" still hit) used to find a
# document's own header row and locate its date/amount columns.
_HEADER_DATE_LABEL_RE = re.compile(r"(datum|date|buch|wert|abrechnung)", re.IGNORECASE)
_HEADER_AMOUNT_LABEL_RE = re.compile(
    r"(betrag|saldo|umsatz|amount|balance|belastung|gutschrift|credit|debit)", re.IGNORECASE
)
# Header words closer together than this (points) are one multi-word column label
# (e.g. "Sender / Empfänger"); farther apart marks a new column. Picked from the
# real gaps seen in test statements: ~2-3pt within a label, 8pt+ between columns.
_COLUMN_GAP_THRESHOLD = 8.0

# Below this fraction of populated cells, a pdfplumber-detected table is treated as a
# failed detection (e.g. a borderless statement collapsed into one text-heavy column)
# rather than a real table, so the financial-anchor fallback gets a chance instead.
_MIN_POPULATED_RATIO = 0.35


def _find_iban(text: str) -> str:
    match = _IBAN_RE.search(text)
    return match.group().replace(" ", "") if match else ""


def _normalize_amount(sign: Optional[str], amount: str, sign_marker: Optional[str]) -> str:
    negative = (sign or "").strip() == "-" or sign_marker == "S"
    return ("-" if negative else "") + amount


def _extract_amounts(text: str) -> List[str]:
    """Finds every currency-tagged amount in text, sign-normalized (leading -/+, or a
    trailing S/H debit-credit marker, all collapse to a plain optionally-negative number)."""
    return [_normalize_amount(sign, amount, marker) for sign, amount, marker in _AMOUNT_RE.findall(text)]


def _parse_first_bare_amount(text: str) -> str:
    match = _BARE_AMOUNT_RE.search(text)
    if not match:
        return ""
    return _normalize_amount(match.group(1), match.group(2), match.group(3))


def _normalize_date(text: str) -> str:
    match = _DATE_RE.search(text)
    if match:
        return match.group()
    match = _SPLIT_DATE_RE.search(text)
    if match:
        return match.group(1) + match.group(2)
    return text.strip()


def _bbox_overlaps(obj: dict, bbox: tuple) -> bool:
    """True if a pdfplumber char/word object overlaps a (x0, top, x1, bottom) bbox."""
    bx0, btop, bx1, bbottom = bbox
    ox0, otop, ox1, obottom = obj["x0"], obj["top"], obj["x1"], obj["bottom"]
    return not (ox1 <= bx0 or ox0 >= bx1 or obottom <= btop or otop >= bbottom)


def _is_degenerate_table(extracted: List[list]) -> bool:
    rows = len(extracted)
    cols = max((len(r) for r in extracted), default=0)
    if rows == 0 or cols <= 1:
        return True
    nonempty = sum(1 for row in extracted for cell in row if cell not in (None, ""))
    if (nonempty / (rows * cols)) < _MIN_POPULATED_RATIO:
        return True
    # A cell packing 2+ dates or 2+ amounts means pdfplumber merged several distinct
    # transactions into one cell (a subtler failure than a mostly-empty grid) — still
    # unusable for financial data, since every value after the first is silently lost.
    for row in extracted:
        for cell in row:
            if not cell:
                continue
            if len(set(_DATE_RE.findall(cell))) >= 2 or len(_extract_amounts(cell)) >= 2:
                return True
    return False


def _page_line_words(page) -> List[List[dict]]:
    """Physical lines on a page as word-dict lists, top-to-bottom, left-to-right within
    a line — keeps each word's x-position so columns can be reconstructed from it."""
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    lines: dict = {}
    for w in words:
        key = round(w["top"], 1)
        lines.setdefault(key, []).append(w)
    return [sorted(ws, key=lambda w: w["x0"]) for _top, ws in sorted(lines.items())]


def _line_text(words: List[dict]) -> str:
    return " ".join(w["text"] for w in words)


def _cluster_header_columns(header_words: List[dict]) -> List[Tuple[str, float]]:
    """Groups adjacent header words into logical columns by horizontal gap, returning
    (label, x_start) per column — e.g. "Sender", "/", "Empfänger" (small gaps) become
    one "Sender / Empfänger" column, while a larger gap starts a new one."""
    groups = [[header_words[0]]]
    for w in header_words[1:]:
        prev = groups[-1][-1]
        if w["x0"] - prev["x1"] > _COLUMN_GAP_THRESHOLD:
            groups.append([w])
        else:
            groups[-1].append(w)
    return [(_line_text(group), group[0]["x0"]) for group in groups]


# Marks a page boundary within a flattened, multi-page line list (see read_pdf).
# Distinct from any real line (which is always a list, possibly empty), so an
# `is` check can't collide with content.
_PAGE_BREAK = None


def _looks_like_header(words: List[dict]) -> bool:
    if words is _PAGE_BREAK or len(words) < 3:
        return False
    text = _line_text(words)
    return bool(_HEADER_DATE_LABEL_RE.search(text) and _HEADER_AMOUNT_LABEL_RE.search(text))


def _find_header_words(lines: List[List[dict]]) -> Optional[List[dict]]:
    """The document's own column-header row: the physical line naming both a
    date-like and an amount-like field (e.g. "Datum ... Betrag ...")."""
    for words in lines:
        if _looks_like_header(words):
            return words
    return None


_COLUMN_BOUNDARY_MARGIN = 6.0


def _column_boundaries(column_starts: List[float]) -> List[float]:
    """Upper bound for each column = the next column's own start minus a small margin
    (not a 50/50 midpoint — a wide column's long value, e.g. a full IBAN, can run most
    of the way to where the next column actually begins, so a midpoint would wrongly
    slice it in half). The margin absorbs small left-drift in a column's own first
    word (font/kerning jitter) without letting it bleed into the previous column.
    Last entry is +inf so the rightmost column always catches everything past it."""
    return [
        column_starts[i + 1] - _COLUMN_BOUNDARY_MARGIN for i in range(len(column_starts) - 1)
    ] + [float("inf")]


def _column_index_for(x0: float, boundaries: List[float]) -> int:
    for i, boundary in enumerate(boundaries):
        if x0 < boundary:
            return i
    return len(boundaries) - 1


def _reconstruct_columned_table(lines: List[List[dict]]) -> Tuple[Optional[List[List[str]]], Optional[str]]:
    """Reconstructs transaction rows using the document's own column positions, derived
    from its header row, so the output mirrors the source layout — same column names and
    order — instead of a generic Date/Amount/Description shape.

    Each word is bucketed into the header column whose x-position it falls under. A
    physical line starts a new row when its date-column bucket begins with a day.month
    pattern; a bare wrapped-down year (no dot) doesn't match that pattern, so a date
    split across two physical lines by a narrow column still lands in one row instead
    of falsely starting a new one.

    Returns (table_rows, preamble_text); (None, None) if no header row is found, it has
    no recognizable date column, or fewer than two rows resulted — the caller then falls
    back to the plainer anchor-based reconstruction.
    """
    header_words = _find_header_words(lines)
    if not header_words:
        return None, None

    columns = _cluster_header_columns(header_words)
    labels = [label for label, _ in columns]
    column_boundaries = _column_boundaries([start for _, start in columns])
    date_cols = {i for i, l in enumerate(labels) if _HEADER_DATE_LABEL_RE.search(l)}
    if not date_cols:
        return None, None
    anchor_date_col = min(date_cols)
    amount_cols = {i for i, l in enumerate(labels) if _HEADER_AMOUNT_LABEL_RE.search(l)}

    preamble_parts: List[str] = []
    # Lines seen before the first transaction row (account title, holder, date range,
    # opening balance) — a multi-page statement repeats this exact block on every page,
    # and it doesn't look like a header (no date+amount keywords) so it isn't caught by
    # the check above. Recognizing repeats by exact text and skipping them keeps that
    # boilerplate from being folded into whatever transaction happens to be open when
    # a new page starts.
    preamble_line_set: set = set()
    rows: List[dict] = []
    current: Optional[dict] = None
    seen_header = False
    # A page boundary is immediately followed by that page's repeated furniture
    # (title, account holder, running balance) before the table resumes — content
    # that doesn't belong to the transaction that happened to be open when the page
    # ended. Everything after a break is discarded until a genuine new row shows up.
    after_page_break = False

    for words in lines:
        if words is _PAGE_BREAK:
            after_page_break = True
            continue
        # Multi-page statements repeat the header on every page — skip every
        # occurrence, not just the first, or a repeat gets folded into whatever
        # transaction was still open and corrupts its amount/date columns.
        if _looks_like_header(words):
            seen_header = True
            continue
        line_text = _line_text(words)
        if line_text in preamble_line_set:
            continue

        buckets: List[List[str]] = [[] for _ in columns]
        for w in words:
            buckets[_column_index_for(w["x0"], column_boundaries)].append(w["text"])

        date_frag = " ".join(buckets[anchor_date_col]).strip()
        is_new_row = bool(_ROW_START_DATE_RE.match(date_frag))

        if after_page_break and not is_new_row:
            continue
        after_page_break = False

        if is_new_row:
            if current:
                rows.append(current)
            current = {i: [] for i in range(len(columns))}
        elif current is None:
            if seen_header:
                preamble_parts.append(line_text)
                preamble_line_set.add(line_text)
            continue

        for i, bucket in enumerate(buckets):
            if bucket:
                current[i].append(" ".join(bucket))

    if current:
        rows.append(current)
    if len(rows) < 2:
        return None, None

    amount_col_order = sorted(amount_cols)
    row_outputs = []
    any_iban = False
    valid_amounts = 0
    valid_dates = 0
    total_amount_slots = len(rows) * len(amount_col_order)
    for r in rows:
        full_text_parts = [" ".join(r.get(i, [])) for i in range(len(columns))]
        # Amount columns are often right-aligned in the source, so a value's left edge
        # can drift into the *previous* column's x-range — bucketing alone misplaces it.
        # Scanning the whole row's text for currency-tagged amounts, in reading order,
        # and assigning them positionally to the amount columns sidesteps that; a column
        # whose own text had no currency marker next to it (e.g. a repeated total with
        # no "EUR" of its own) falls back to reading its own bucket directly.
        row_amounts = _extract_amounts(" ".join(full_text_parts))
        amount_values = {}
        ai = 0
        for col_i in amount_col_order:
            if ai < len(row_amounts):
                amount_values[col_i] = row_amounts[ai]
                ai += 1
            else:
                amount_values[col_i] = _parse_first_bare_amount(full_text_parts[col_i])
            if amount_values[col_i]:
                valid_amounts += 1

        row_out = []
        for i in range(len(columns)):
            if i in date_cols:
                value = _normalize_date(full_text_parts[i])
                if i == anchor_date_col and _DATE_RE.fullmatch(value):
                    valid_dates += 1
                row_out.append(value)
            elif i in amount_cols:
                row_out.append(amount_values[i])
            else:
                row_out.append("\n".join(r.get(i, [])))
        iban = _find_iban(" ".join(full_text_parts))
        any_iban = any_iban or bool(iban)
        row_out.append(iban)
        row_outputs.append(row_out)

    # Sanity gate: if amount/date columns mostly failed to parse, this document's
    # layout doesn't actually fit the column model we built — don't ship a table with
    # silently wrong or missing financial values, fall back to the plainer reconstruction.
    if total_amount_slots and valid_amounts / total_amount_slots < 0.9:
        return None, None
    if valid_dates / len(rows) < 0.9:
        return None, None

    header_row = labels + ["IBAN"]
    if not any_iban:
        header_row = header_row[:-1]
        row_outputs = [r[:-1] for r in row_outputs]

    table = [header_row] + row_outputs
    preamble = "\n".join(preamble_parts) if preamble_parts else None
    return table, preamble


def _reconstruct_financial_table(lines: List[str]) -> Tuple[Optional[List[List[str]]], Optional[str]]:
    """Groups a borderless statement's physical text lines into transaction rows.

    A line carrying a decimal amount anchors a new transaction; lines without one
    (wrapped names, addresses, reference codes) are appended to the current
    transaction's free-text column rather than guessed into a specific field —
    guessing a column for a name vs. a payment purpose isn't reliable across
    different banks' export layouts, but dates and amounts must never be misattributed
    since this feeds financial records.

    `lines` may span multiple pages concatenated in reading order, so a transaction
    split across a page break still ends up as one row, and the whole document
    produces a single continuous table instead of one repeated per page.

    Returns (table_rows, preamble_text). table_rows is None if fewer than two
    transaction anchors were found (not worth treating as a table).
    """
    preamble_parts: List[str] = []
    rows: List[dict] = []
    current: Optional[dict] = None

    for line_text in lines:
        amounts = _extract_amounts(line_text)
        date_match = _DATE_RE.search(line_text)
        # A new transaction anchor needs BOTH a date and an amount on the same line.
        # An amount alone also matches page-footer summary lines (running balance,
        # interest/repayment totals) that carry no date — those must fold into the
        # preceding transaction's text, not spawn a bogus row that corrupts sums.
        if amounts and date_match:
            if current:
                rows.append(current)
            current = {
                "date": date_match.group(),
                "amounts": amounts,
                "iban": _find_iban(line_text),
                "text_parts": [line_text],
            }
        elif current is not None:
            current["text_parts"].append(line_text)
            if not current["iban"]:
                current["iban"] = _find_iban(line_text)
        else:
            preamble_parts.append(line_text)

    if current:
        rows.append(current)
    if len(rows) < 2:
        return None, None

    max_amounts = max(len(r["amounts"]) for r in rows)
    header = ["Date"] + [f"Amount {i + 1}" for i in range(max_amounts)] + ["IBAN", "Description"]
    table = [header]
    for r in rows:
        amount_cells = r["amounts"] + [""] * (max_amounts - len(r["amounts"]))
        table.append([r["date"]] + amount_cells + [r["iban"], "\n".join(r["text_parts"])])

    preamble = "\n".join(preamble_parts) if preamble_parts else None
    return table, preamble


def read_pdf(path: str) -> List[Block]:
    blocks: List[Block] = []
    # Lines from consecutive pages that have no usable pdfplumber table, queued so a
    # transaction split across a page break — and the statement's header row — are
    # handled once for the whole run instead of once per page.
    pending_lines: List[List[dict]] = []

    def flush_pending() -> None:
        if not pending_lines:
            return
        # Prefer reconstructing real columns from the document's own header row; only
        # fall back to the generic date+amount anchor shape (or, failing that, plain
        # text) when no header row can be found or matched to a date column.
        recon_table, preamble = _reconstruct_columned_table(pending_lines)
        if not recon_table:
            recon_table, preamble = _reconstruct_financial_table(
                [_line_text(words) for words in pending_lines if words is not _PAGE_BREAK]
            )
        if recon_table:
            if preamble:
                blocks.append(("text", preamble))
            blocks.append(("table", recon_table))
        else:
            blocks.append((
                "text",
                "\n".join(_line_text(words) for words in pending_lines if words is not _PAGE_BREAK),
            ))
        pending_lines.clear()

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            found_tables = page.find_tables()
            good_tables = [t for t in found_tables if not _is_degenerate_table(t.extract())]

            if good_tables:
                flush_pending()
                for table in good_tables:
                    extracted = table.extract()
                    cleaned = [["" if cell is None else cell for cell in row] for row in extracted]
                    blocks.append(("table", cleaned))
                table_bboxes = [t.bbox for t in good_tables]
                text_page = page.filter(
                    lambda obj: not any(_bbox_overlaps(obj, bbox) for bbox in table_bboxes)
                )
                text = text_page.extract_text()
                if text:
                    blocks.append(("text", text))
            else:
                if pending_lines:
                    pending_lines.append(_PAGE_BREAK)
                pending_lines.extend(_page_line_words(page))
        flush_pending()
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
