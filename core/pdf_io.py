import re
import pdfplumber
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from core.types import Block
from typing import List, Optional, Tuple

# Anchors a line as a financial transaction row: a European-style decimal-comma
# amount immediately next to a currency code (e.g. "1.234,56 EUR" or "-12,34EUR"),
# optionally with a trailing German Haben/Soll debit-credit marker glued to the
# number itself (e.g. "2.373,80H EUR" credit, "138,19S EUR" debit — some banks
# encode the sign as this letter instead of a leading minus). Requiring the
# currency suffix is what tells a real amount apart from a same-shaped number
# elsewhere in the line — e.g. an invoice reference like "RE.476,29" that would
# otherwise be mistaken for a second amount and shift every column after it.
_AMOUNT_RE = re.compile(r"(-?\d{1,3}(?:\.\d{3})*,\d{2})([HS])?\s*(?:EUR|USD|GBP|CHF|RSD)\b")
_DATE_RE = re.compile(r"\b\d{2}\.\d{2}\.\d{4}\b")
# IBANs appear either compact ("DE76550104001041824990") or human-readable with a
# space every 4 characters ("DE75 1203 0000 0001 2987 77") — both must match.
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[A-Z0-9]{10,30}|(?:\s[A-Z0-9]{2,4}){2,8})\b")

# Below this fraction of populated cells, a pdfplumber-detected table is treated as a
# failed detection (e.g. a borderless statement collapsed into one text-heavy column)
# rather than a real table, so the financial-anchor fallback gets a chance instead.
_MIN_POPULATED_RATIO = 0.35


def _find_iban(text: str) -> str:
    match = _IBAN_RE.search(text)
    return match.group().replace(" ", "") if match else ""


def _extract_amounts(text: str) -> List[str]:
    """Finds every currency-tagged amount in text, sign-normalized (S marker -> negative)."""
    amounts = []
    for amount, sign_marker in _AMOUNT_RE.findall(text):
        if sign_marker == "S" and not amount.startswith("-"):
            amount = "-" + amount
        amounts.append(amount)
    return amounts


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


def _page_lines(page) -> List[str]:
    """Physical text lines on a page, top-to-bottom, words left-to-right within a line."""
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    lines: dict = {}
    for w in words:
        key = round(w["top"], 1)
        lines.setdefault(key, []).append(w)
    return [
        " ".join(w["text"] for w in sorted(ws, key=lambda w: w["x0"]))
        for _top, ws in sorted(lines.items())
    ]


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
        table.append([r["date"]] + amount_cells + [r["iban"], " ".join(r["text_parts"])])

    preamble = "\n".join(preamble_parts) if preamble_parts else None
    return table, preamble


def read_pdf(path: str) -> List[Block]:
    blocks: List[Block] = []
    # Lines from consecutive pages that have no usable pdfplumber table, queued so a
    # transaction split across a page break — and the statement's header row — are
    # handled once for the whole run instead of once per page.
    pending_lines: List[str] = []

    def flush_pending() -> None:
        if not pending_lines:
            return
        recon_table, preamble = _reconstruct_financial_table(pending_lines)
        if recon_table:
            if preamble:
                blocks.append(("text", preamble))
            blocks.append(("table", recon_table))
        else:
            blocks.append(("text", "\n".join(pending_lines)))
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
                pending_lines.extend(_page_lines(page))
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
