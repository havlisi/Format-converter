# Visual-fidelity conversions: PDF→DOCX layout preservation + PDF→XLSX surrounding text

Design spec. Written 2026-08-31.

## Problem

The converter's stated scope is "content-fidelity (text + tables), not pixel-perfect
layout". Every conversion runs through one lossy model:

    read_X(path) -> List[Block]      # Block = ("text", str) | ("table", List[List[str]])
    write_Y(blocks, path)

That model carries no fonts, no positions, no styling, no page geometry. Two real needs
aren't met by it:

1. **PDF → DOCX** must preserve the visual layout of the source — fonts, text placement,
   tables, and images — so the Word file looks like the PDF, not a reflowed text dump.
   This is the higher priority of the two.
2. **PDF → XLSX** must keep the text that sits *around* the transaction table (account
   holder, IBAN/BIC, statement period, opening/closing balance, any footer notes), not
   just the table rows. Today the borderless-statement reconstruction path keeps only a
   "preamble" (lines before the first transaction) and folds or drops everything after
   the last row.

Out of scope (explicitly dropped during design): DOCX → PDF, XLSX → PDF, and any
"pixel-perfect" output whose target is a grid format (XLSX/CSV have no page).

## Approach

### PDF → DOCX — direct route via `pdf2docx`

`pdf2docx` (pip, pure Python, built on PyMuPDF) reconstructs paragraphs, text styling,
tables, and images with their positions on the page. It is purpose-built for exactly
this conversion and is the best fidelity available without requiring MS Office or a
LibreOffice install on every machine.

It does **not** fit the Block pipeline — it reads the PDF and writes the DOCX itself. So
`dispatch.convert` gains a **direct-route table**, checked before the generic
reader/writer path:

```python
_DIRECT_ROUTES = {
    ("pdf", "docx"): docx_io.pdf_to_docx,   # (source_path, target_path) -> None
}

def convert(source_path, target_ext):
    source_ext = ext_of(source_path)
    target_ext = target_ext.lower()
    # ... existing validation ...
    route = _DIRECT_ROUTES.get((source_ext, target_ext))
    if route:
        target_path = output_path_for(source_path, target_ext)
        route(source_path, target_path)
        return target_path
    # ... existing block pipeline unchanged ...
```

`_pdf_to_docx` lives in `core/docx_io.py` (keeps DOCX-writing knowledge in one module):

```python
def pdf_to_docx(pdf_path: str, docx_path: str) -> None:
    from pdf2docx import Converter
    if not _pdf_has_text_layer(pdf_path):
        # A scan has no layout to preserve — it's page images. Route through the
        # existing OCR block pipeline so the DOCX at least carries searchable text.
        from core import pdf_io
        blocks = pdf_io.read_pdf(pdf_path)   # OCR fallback already lives here
        write_docx(blocks, docx_path)
        return
    cv = Converter(pdf_path)
    try:
        cv.convert(docx_path)   # all pages
    finally:
        cv.close()
```

`_pdf_has_text_layer` opens the PDF with pdfplumber and returns `True` if any page
yields words via the existing `pdf_io._page_line_words`. This reuses code already
proven against the real statement files.

### PDF → XLSX — keep all non-row text

Stay inside the Block model. The fix is in `pdf_io.read_pdf` / `flush_pending`: emit
**every** region of non-transaction text as its own `("text", ...)` block, in reading
order relative to the table, instead of only the leading preamble.

Concretely, `_reconstruct_columned_table` and `_reconstruct_financial_table` already
separate row lines from non-row lines internally. Extend them (or `flush_pending`
around them) to return three parts instead of two:

- `preamble` — non-row lines before the first row (already returned)
- `table` — the reconstructed rows (already returned)
- `trailing` — non-row lines after the last row (**new**; currently discarded or
  folded into the last row's Description)

`flush_pending` then appends `("text", preamble)`, `("table", table)`,
`("text", trailing)` in that order. `write_xlsx` already renders a `text` block as one
row per line (the existing 32k-char-truncation fix), and `_autofit_columns` already
skips single-cell "banner" rows when sizing columns — so no `xlsx_io` change is
needed for the rows to land correctly around the table.

Label/value lines that today get swallowed by `_reconstruct_financial_table`'s
Description column (e.g. "IBAN: DE..", "Zeitraum: 01.01.2026 – 31.01.2026",
"Anfangssaldo 1.234,56") are non-row lines by definition — they carry no row-start
date — so they flow into `preamble`/`trailing` automatically once those are captured.
No new keyword list.

The native-grid-table branch (`good_tables`) already captures out-of-bbox text as a
`("text", text)` block after the table (pdf_io.py:874) — unchanged.

## Components touched

| File | Change |
|---|---|
| `core/dispatch.py` | Add `_DIRECT_ROUTES` table + check in `convert()` before the block pipeline. ~8 lines. |
| `core/docx_io.py` | Add `pdf_to_docx(pdf_path, docx_path)` + `_pdf_has_text_layer`. |
| `core/pdf_io.py` | `_reconstruct_columned_table` / `_reconstruct_financial_table` / `flush_pending`: capture trailing non-row text, emit as a `text` block after the table. |
| `requirements.txt` | Add `pdf2docx`. |
| `README.md` | Rewrite the scope line: content-fidelity by default; **PDF→DOCX preserves page layout** via pdf2docx; note the scan caveat. |
| `HANDOFF.md` | Note the new direct-route mechanism in `dispatch`, the pdf2docx dependency (and its PyMuPDF/AGPL transitive dep), and the scan fallback. |

`batch.py`, `app.py`, `ui/index.html` — unchanged. The GUI already lists `docx` as a
target; nothing about the direct route is visible to the frontend.

## Data flow

**PDF → DOCX, text-layer PDF:**
`convert()` → `_DIRECT_ROUTES[("pdf","docx")]` → `docx_io.pdf_to_docx` →
`_pdf_has_text_layer` = True → `pdf2docx.Converter.convert` writes the DOCX directly.
Block pipeline not entered.

**PDF → DOCX, scanned PDF:**
`convert()` → `pdf_to_docx` → `_pdf_has_text_layer` = False → `pdf_io.read_pdf`
(existing OCR path) → `write_docx(blocks)`. Layout not preserved (there is none — it's
images), but the DOCX carries OCR'd text.

**PDF → XLSX:**
`convert()` → block pipeline (unchanged entry) → `read_pdf` now yields
`[("text", preamble), ("table", rows), ("text", trailing)]` → `write_xlsx` lays them
as banner rows / grid / banner rows.

**All other pairs:** unchanged.

## Error handling

- `pdf2docx` raises on a corrupt/encrypted PDF. Let it propagate — `batch.run_batch`
  already catches per-file exceptions and reports them in the UI status column; the
  batch continues with the next file.
- `pdf2docx` import failure (dependency not installed) surfaces as `ModuleNotFoundError`
  with the module name — same failure shape as the existing `pytesseract` path. The
  README setup step covers `pip install -r requirements.txt`.
- A text-layer PDF that `pdf2docx` converts to a visually poor DOCX (very complex
  layout) is **not** an error — it's a known fidelity limit, documented, verified by
  eye per the HANDOFF methodology. No automatic quality gate.
- `_pdf_has_text_layer` on an unreadable PDF: pdfplumber raises; propagate (same as
  today's `read_pdf`).

## Testing

**`tests/test_dispatch.py`** — new:
- `("pdf","docx")` routes to the direct function, not `read_pdf`+`write_docx`
  (monkeypatch both, assert which is called).
- Every other `(source, target)` pair still routes through the block pipeline.

**`tests/test_docx_io.py`** — new:
- `pdf_to_docx` on a tiny generated text-layer PDF (reportlab, one styled paragraph +
  a 2×2 table) produces a `.docx` that python-docx opens; assert the paragraph text and
  the table cell values survive. Not a pixel assertion — a smoke + content check.
- `pdf_to_docx` on an image-only PDF (no text layer) falls back: monkeypatch
  `pdf_io.read_pdf` to a sentinel block list, assert `write_docx` received it.

**`tests/test_pdf_io.py`** — extend:
- Synthetic line fixtures (same dict shape the existing tests use) with non-row text
  *after* the last transaction: assert `read_pdf` emits a trailing `("text", ...)`
  block containing those lines.
- Label/value lines mixed around a reconstructed table land in `text` blocks, not in a
  table cell.
- Regression: the existing "orphan line before first row" and "footer must not corrupt
  date" tests still pass (trailing-capture must not re-open the merged-total-line bug
  documented in HANDOFF).

**Manual, per HANDOFF "Verifying changes":**
- Convert 3–4 real statements from `../Test converter` PDF→DOCX; open in Word, compare
  side-by-side with the PDF for layout drift.
- Convert the same PDF→XLSX; confirm holder/IBAN/period/saldo text now appears above
  and below the table.

`python -m pytest tests/ -v` must stay green (65 tests + the new ones).

## Known limitations (add to README + HANDOFF)

- Scanned (image-only) PDF → DOCX carries OCR text only, no layout — there is no text
  layout in a scan to preserve.
- `pdf2docx` fidelity on very complex multi-column / heavily-graphical PDFs is good but
  not perfect; verify by eye for anything that matters.
- New transitive dependency **PyMuPDF** (via `pdf2docx`) is AGPL-licensed. Fine for
  internal use; revisit if the tool is ever distributed commercially.
- PDF → XLSX surrounding text is captured as flat banner rows in reading order, not
  positioned or styled — it's readable context next to the table, not a layout copy.

## YAGNI / deferred

- No MS Word COM automation path (needs licensed Office on every machine).
- No LibreOffice headless route (350 MB external install; worse PDF-import fidelity
  than pdf2docx for text PDFs).
- No DOCX→PDF, XLSX→PDF.
- No per-conversion quality scoring / automatic fallback on "looks bad".
- No config knob for direct-route on/off — the route is always better when it applies.
