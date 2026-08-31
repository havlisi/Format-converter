# Format Converter

Batch-converts between PDF, XLSX, DOCX, CSV. Content-fidelity (text + tables) by default. **PDF → DOCX
preserves the source page layout** (fonts, text position, tables, images) via `pdf2docx`; a scanned PDF
with no text layer is converted through OCR to searchable text with no layout. **PDF → XLSX** places the
reconstructed transaction table first, then appends every non-row line found around it (holder, IBAN,
period, balances, footers) as plain rows below.

## Setup

    cd converter
    pip install -r requirements.txt

Scanned PDFs (no text layer) also need [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) installed
separately (`winget install UB-Mannheim.TesseractOCR` on Windows) — `pip install` alone doesn't provide it. Without
it, a scanned PDF fails with a clear message telling you to install it; a normal text-layer PDF works either way.

`pip install -r requirements.txt` also installs `pdf2docx` (and its dependency **PyMuPDF**, which is
**AGPL-licensed** — fine for internal use, revisit before any commercial redistribution).

## Run

    python app.py

## Run tests

    python -m pytest tests/ -v

## Known limitations

- Scanned (image-only) PDFs are converted via OCR (Tesseract), which is meaningfully less reliable than a real text
  layer — digit misreads (0/O, 1/l, 6/8, ...) are a real risk no OCR engine fully eliminates. **Always spot-check
  OCR'd numbers against the original scan before trusting them for financial records.** A word Tesseract itself
  flagged as low-confidence is wrapped in `¿...?` in the output so it stands out as worth checking rather than being
  presented as plain, trustworthy text.
- Content-fidelity, not pixel-perfect: fonts, colors, images, and exact page layout aren't reproduced —
  **except PDF → DOCX**, which does preserve the source page layout via `pdf2docx` (see the scope note above).
- Scanned PDF → DOCX carries OCR text only, with no layout (a scan has no text layout to preserve).
- `pdf2docx` layout fidelity on very complex multi-column or heavily graphical PDFs is good but not exact —
  verify by eye for anything that matters.
- PDF → XLSX context text is flat rows in reading order below the table, not a positioned copy. A wrapped
  continuation of the *last* transaction's description may appear in that block instead of the last cell.
- A source file with no extractable content (e.g. a blank PDF) reports an error rather than producing an empty output.
- Multi-sheet XLSX → CSV concatenates all sheets into one file, separated by a blank row; sheet names aren't preserved.
- Borderless financial statements (bank/transaction exports with no ruling lines) are reconstructed row-by-row. When
  the document has its own column-header row (e.g. "Datum ... Betrag Saldo"), the real columns are rebuilt from its
  word positions, so the output mirrors the source layout. If no header is found, or the reconstructed columns don't
  hold up (most amount/date cells fail to parse), it falls back to a generic Date/Amount/IBAN/Description shape built
  from each transaction's date + currency-tagged amount anchor — payee, purpose, and reference codes are kept as one
  merged "Description" column rather than guessed into separate fields, since that split isn't reliable across every
  bank's export layout. Dates and amounts are the parts that must never be misattributed.
- Transaction dates are recognized either dot-separated (`DD.MM.YYYY`, or `DD.MM.` with the year wrapped onto the
  next line) or slash-separated (`DD/MM/YYYY`, or `DD/MM` with no year on the line at all — the year is then
  inferred from the first full date found earlier in the document, e.g. a statement period like
  "Vom 01/03/2025 bis zum 31/03/2025").
- Amounts are recognized in European (`1.234,56`) or international (`1,234.56`) notation, with an optional leading
  sign or trailing German Haben/Soll marker (`H`/`S`), each either glued to the number or separated by a space. A
  debit/credit column pair (e.g. "Belastung"/"Gutschrift", "Soll"/"Haben") — where only one side is ever populated
  per row — is routed by the amount's own sign rather than assumed to always fill the first column.
- Documents that aren't row-per-transaction (e.g. one transaction described per page as label/value pairs, with its
  date and amount landing on the same line) still get a Date/Amount/IBAN/Description row per transaction via the
  generic fallback — the surrounding label/value fields aren't split into their own columns, just kept as readable
  text, since there's no repeating header row to derive a real column layout from.
- If the source PDF's own font renders two adjacent header cells with zero space between them (a defect in the PDF
  itself, not something we control), the header labels split at wherever pdfplumber happens to break the run rather
  than at the real label boundaries — the transaction data below is unaffected, only those header names are garbled.
