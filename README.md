# Format Converter

Batch-converts between PDF, XLSX, DOCX, CSV. Content-fidelity (text + tables), not pixel-perfect layout. Text-layer PDFs only — no OCR.

## Setup

    cd converter
    pip install -r requirements.txt

## Run

    python app.py

## Run tests

    python -m pytest tests/ -v

## Known limitations

- Text-layer PDFs only — scanned/image PDFs raise an error (no OCR).
- Content-fidelity, not pixel-perfect: fonts, colors, images, and exact page layout aren't reproduced.
- A source file with no extractable content (e.g. a blank PDF) reports an error rather than producing an empty output.
- Multi-sheet XLSX → CSV concatenates all sheets into one file, separated by a blank row; sheet names aren't preserved.
