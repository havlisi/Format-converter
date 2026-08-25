# Handoff notes — Format Converter

Context for picking this project back up without re-deriving everything. Written 2026-08-25.

## What this is

Batch converter between PDF, XLSX, DOCX, CSV (Tkinter GUI, `python app.py`). Core logic in
`core/` (one reader/writer module per format), dispatched via `core/dispatch.py`. Repo:
https://github.com/havlisi/Format-converter (pushed via `git subtree split --prefix=converter`
from the monorepo at `C:\Users\Isidora\Isis\claude` — that repo mixes in an unrelated project,
so **never** push its `master` directly; always re-run the subtree split and push
`converter-only:main`. See "Pushing updates" below.)

The hard part of this project — and where almost all the recent work went — is
**`core/pdf_io.py`**: converting real-world bank/financial statement PDFs to XLSX accurately.
Financial accuracy is the top priority the user cares about; when in doubt, code prefers to
fall back to safe, unstructured plain text over shipping a wrong or misattributed number.

## PDF → table reconstruction architecture (`core/pdf_io.py`)

Three layers, tried in order, each falling back to the next on failure:

1. **`good_tables`** — pdfplumber's own `find_tables()`, used as-is when it finds a real
   grid-lined table that isn't degenerate (`_is_degenerate_table`: catches both "mostly empty
   grid" and "cell packs 2+ dates/amounts because pdfplumber merged distinct rows into one
   cell").
2. **`_reconstruct_columned_table`** — the primary path for borderless statements. Finds the
   document's own header row (a line naming both a date-like and amount-like column, e.g.
   "Datum ... Betrag Saldo"), clusters header words into columns by x-gap
   (`_COLUMN_GAP_THRESHOLD = 6.0`), buckets every word by x-position into those columns, and
   groups physical lines into rows via `_ROW_START_DATE_RE` (a line whose date-column bucket
   begins with a day.month pattern starts a new row). Produces real column names matching the
   source document. Has a **sanity gate**: if amount/date cells mostly fail to parse, or a
   validation heuristic (see below) can't be satisfied, returns `None` and the caller falls
   back to step 3. Also handles: multi-page statements (page-break sentinel `_PAGE_BREAK`,
   repeated-boilerplate skipping), OCR'd pages (same word-dict shape, see below), debit/credit
   split column pairs (routes a lone amount by its own sign, not position), slash dates with
   year inferred from elsewhere in the document.
3. **`_reconstruct_financial_table`** — generic fallback. Anchors each transaction on a line
   carrying **both** a date and a currency-tagged amount; everything else folds into one
   "Description" column rather than being guessed into named fields (guessing payee vs.
   purpose isn't reliable across bank layouts, but the amount/date must never be
   misattributed). This is what handles one-transaction-per-page label/value reports too now
   (the date+amount just needs to land on the same physical line).
4. If even that fails: raw text, one block, no structure. Still shows the user everything —
   never silently drops content.

**Validation gate details worth remembering** (in `_reconstruct_columned_table`): a 2-amount-
column layout is either a debit/credit split (exactly one populated per row, e.g.
Belastung/Gutschrift) or a running-total pair where **both** should always be present (e.g.
Betrag/Saldo). These look identical on any single row with 1 amount found — the code
disambiguates by checking whether *any* row in the whole document ever produced 2 amounts at
once. Get this wrong and a systematic single-column extraction failure (e.g. Saldo silently
never captured) passes validation undetected — this was a real bug, fixed, and is exactly the
kind of regression to watch for if this logic is touched again.

**OCR** (`_ocr_page_line_words`): a page with no text layer but an embedded image gets rendered
(pdfplumber's `to_image()`, no external tool needed beyond Tesseract) and run through
`pytesseract.image_to_data`, converting output into the same `{text, x0, x1, top, bottom}`
word-dict shape as pdfplumber's own `extract_words()` — so every downstream reconstruction step
treats an OCR'd page exactly like a normal one. Low-confidence words get wrapped in `¿...?`.
Requires Tesseract installed separately (`winget install UB-Mannheim.TesseractOCR`); auto-
detects the default Windows install path if not yet on PATH.

## Known limitations (also in README.md — keep both in sync if this changes)

- OCR is meaningfully less reliable than a real text layer. Always spot-check.
- A source PDF whose own font renders two header words with zero gap between them (a defect in
  the PDF itself) can produce a garbled header label — data below is unaffected, seen once
  (Herkules test file) and not fixable from our side.
- Non-tabular documents (label/value pairs) get date/amount/IBAN extracted but not fully
  column-split.

## Real test files used this session (NOT in the repo — personal financial data)

These live on the user's machine under `C:\Users\Isidora\Downloads\` and
`C:\Users\Isidora\Isis\Bank statement apka\` — never commit them. If continuing PDF work, ask
the user to re-share relevant ones. Formats covered so far, for reference: Sparkasse (dot
dates, Betrag/Saldo), Aareal, StarMoney/HAASE export (H/S suffix, repeated multi-page header),
Qonto (slash dates, no year per row, Belastung/Gutschrift split, international decimal
notation), RaiBa (native grid table), a "Transaction Details" one-per-page US-format report,
and two scanned (OCR-only) statements.

## Verifying changes to `pdf_io.py`

No committed fixtures replicate the real bank files (privacy), so regression-check by hand
against whichever real files are available: run `read_pdf` + `write_xlsx`, check `dims`, and
for anything with a running balance column, verify `Saldo[i] == Saldo[i-1] + Betrag[i]` for
every row (this caught real bugs — a clean 0-mismatch chain is strong evidence of correctness,
better than eyeballing). The unit tests (`tests/test_pdf_io.py`) cover synthetic borderless-
statement fixtures and should still pass (`python -m pytest tests/ -v`, 50 tests).

## Pushing updates to GitHub

From `C:\Users\Isidora\Isis\claude` (the monorepo root, not `converter/`):

    git branch -D converter-only          # if it already exists locally
    git subtree split --prefix=converter -b converter-only
    git push origin converter-only:main

`origin` is already set to `https://github.com/havlisi/Format-converter.git`.

## State as of last session

Working tree clean, nothing uncommitted, local `converter-only` matches `origin/main` exactly.
All 15 real test files (13 text-layer + 2 scanned) convert without crashing; the ones with
verifiable running-balance columns reconcile exactly.
