# Format Converter

Batch-converts between PDF, XLSX, DOCX, CSV. Content-fidelity (text + tables), not pixel-perfect layout.

## Setup

    cd converter
    pip install -r requirements.txt

Scanned PDFs (no text layer) also need [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) installed
separately (`winget install UB-Mannheim.TesseractOCR` on Windows) — `pip install` alone doesn't provide it. Without
it, a scanned PDF fails with a clear message telling you to install it; a normal text-layer PDF works either way.

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
- Content-fidelity, not pixel-perfect: fonts, colors, images, and exact page layout aren't reproduced.
- A source file with no extractable content (e.g. a blank PDF) reports an error rather than producing an empty output.
- Multi-sheet XLSX → CSV concatenates all sheets into one file, separated by a blank row; sheet names aren't preserved.
- Borderless financial statements (bank/transaction exports with no ruling lines) are reconstructed row-by-row. When
  the document has its own column-header row (e.g. "Datum ... Betrag Saldo"), the real columns are rebuilt from its
  word positions, so the output mirrors the source layout. If no header is found, or the reconstructed columns don't
  hold up (most amount/date cells fail to parse), it falls back to a generic Date/Amount/IBAN/Description shape built
  from each transaction's date + currency-tagged amount anchor — payee, purpose, and reference codes are kept as one
  merged "Description" column rather than guessed into separate fields, since that split isn't reliable across every
  bank's export layout. Dates and amounts are the parts that must never be misattributed.
- Transaction dates must be dot-separated (`DD.MM.YYYY`, or `DD.MM.` with the year wrapped onto the next line) and
  carry their own year — a slash format (`DD/MM`) or a date with the year stated only once for the whole document
  isn't recognized as a row yet, so those statements fall back to plain text.
- Amounts are recognized in European (`1.234,56`) or international (`1,234.56`) notation, with an optional leading
  sign or trailing German Haben/Soll marker (`H`/`S`), each either glued to the number or separated by a space.
- Documents that aren't row-per-transaction (e.g. one transaction described per page as label/value pairs) aren't
  restructured into a table — the text is preserved, just not split into columns.
