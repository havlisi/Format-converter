# PDF→DOCX layout preservation + PDF→XLSX surrounding text — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PDF→DOCX conversions preserve the source page layout (fonts, positions, tables, images); PDF→XLSX conversions place the reconstructed table first and then append every non-row line the extractor found around it.

**Architecture:** Add a direct-route table to `core/dispatch.py` that bypasses the lossy `Block` pipeline for `(pdf, docx)` and hands the file to `pdf2docx`. Scanned PDFs (no text layer) fall back to the existing OCR `Block` pipeline into `write_docx`. For PDF→XLSX, the two borderless-statement reconstructors in `core/pdf_io.py` each return a new third value — the text they did **not** turn into rows — which `flush_pending` emits as a `("text", ...)` block placed *after* the `("table", ...)` block.

**Tech Stack:** Python 3, pdfplumber, pdf2docx (new; pulls PyMuPDF), openpyxl, python-docx, reportlab (tests only), pytest.

**Spec:** `docs/superpowers/specs/2026-08-31-pdf-docx-xlsx-visual-fidelity-design.md`

## Global Constraints

- `python -m pytest tests/ -v` must pass at the end of every task (65 existing tests + new ones).
- Financial accuracy outranks structure: never move or drop a number to make layout nicer. When unsure, keep raw text.
- No new external binary dependency. `pdf2docx` is pip-only; it is added to `requirements.txt`.
- `pdf2docx` pulls **PyMuPDF**, which is **AGPL-licensed**. Acceptable for internal use only — note it in README and HANDOFF, do not silently bury it.
- Do not touch `app.py`, `batch.py`, `ui/index.html`. The GUI already offers `docx` as a target.
- Repo: `C:\Users\Isidora\Isis\Claude apps\Converter app\Format-converter` (standalone; `origin` = havlisi/Format-converter). Commit locally per task; pushing is out of scope for this plan.

---

### Task 1: Add `pdf2docx` and a text-layer `pdf_to_docx` in `docx_io.py`

**Files:**
- Modify: `requirements.txt`
- Modify: `core/docx_io.py`
- Test: `tests/test_docx_io.py`

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `docx_io.pdf_to_docx(pdf_path: str, docx_path: str) -> None` — converts a PDF with a real text layer to a layout-preserving `.docx`. (Scanned-PDF handling is added in Task 2; this task assumes a text layer.)

- [ ] **Step 1: Add the dependency**

In `requirements.txt`, add a line after `pdfplumber`:

```
pdf2docx
```

- [ ] **Step 2: Install it**

Run: `python -m pip install -r requirements.txt`
Expected: `pdf2docx` and `PyMuPDF` install with no error. Confirm: `python -c "import pdf2docx, fitz; print('ok')"` prints `ok`.

- [ ] **Step 3: Write the failing test**

Add to `tests/test_docx_io.py`. This helper builds a tiny real PDF with a styled paragraph and a table, using reportlab (already a dependency):

```python
import os
from docx import Document
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from core import docx_io


def _make_text_pdf(path):
    doc = SimpleDocTemplate(path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Kontoauszug Nr. 7", styles["Title"]),
        Paragraph("Kontoinhaber: Musterfirma GmbH", styles["Normal"]),
        Spacer(1, 12),
        Table([["Datum", "Betrag"], ["01.03.2026", "1.234,56"], ["02.03.2026", "-99,00"]]),
    ]
    doc.build(story)


def test_pdf_to_docx_preserves_text_and_table(tmp_path):
    pdf = str(tmp_path / "src.pdf")
    out = str(tmp_path / "src.docx")
    _make_text_pdf(pdf)

    docx_io.pdf_to_docx(pdf, out)

    assert os.path.exists(out)
    doc = Document(out)
    all_text = "\n".join(p.text for p in doc.paragraphs)
    all_text += "\n".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert "Kontoinhaber: Musterfirma GmbH" in all_text
    assert "1.234,56" in all_text
    assert "02.03.2026" in all_text
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/test_docx_io.py::test_pdf_to_docx_preserves_text_and_table -v`
Expected: FAIL — `AttributeError: module 'core.docx_io' has no attribute 'pdf_to_docx'`.

- [ ] **Step 5: Implement `pdf_to_docx`**

Add to `core/docx_io.py` (import stays local to the function so a missing dependency only breaks this one path, matching how `pdf_io` imports `pytesseract` lazily):

```python
def pdf_to_docx(pdf_path: str, docx_path: str) -> None:
    """Convert a PDF to DOCX preserving page layout (fonts, positions, tables,
    images) via pdf2docx. A scanned PDF with no text layer has no layout to
    preserve — that case is handled by the caller-facing wrapper in Task 2."""
    from pdf2docx import Converter

    cv = Converter(pdf_path)
    try:
        cv.convert(docx_path)
    finally:
        cv.close()
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_docx_io.py::test_pdf_to_docx_preserves_text_and_table -v`
Expected: PASS.

- [ ] **Step 7: Full suite**

Run: `python -m pytest tests/ -v`
Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add requirements.txt core/docx_io.py tests/test_docx_io.py
git commit -m "feat: pdf_to_docx — layout-preserving PDF to DOCX via pdf2docx"
```

---

### Task 2: Scanned-PDF fallback for `pdf_to_docx`

**Files:**
- Modify: `core/docx_io.py`
- Test: `tests/test_docx_io.py`

**Interfaces:**
- Consumes: `docx_io.pdf_to_docx` from Task 1; `pdf_io.read_pdf(path) -> List[Block]` (existing, already OCRs image-only pages internally); `docx_io.write_docx(blocks, path)` (existing).
- Produces: `docx_io._pdf_has_text_layer(pdf_path: str) -> bool`. Updated `pdf_to_docx` that routes a no-text-layer PDF through `read_pdf` + `write_docx` instead of pdf2docx.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_docx_io.py`:

```python
def test_pdf_to_docx_scanned_falls_back_to_block_pipeline(tmp_path, monkeypatch):
    pdf = str(tmp_path / "scan.pdf")
    out = str(tmp_path / "scan.docx")
    # content doesn't matter — we force the "no text layer" branch
    open(pdf, "wb").write(b"%PDF-1.4\n%%EOF\n")

    monkeypatch.setattr(docx_io, "_pdf_has_text_layer", lambda p: False)
    sentinel = [("text", "OCR line one"), ("table", [["a", "b"]])]
    monkeypatch.setattr("core.pdf_io.read_pdf", lambda p: sentinel)

    called = {}
    real_write = docx_io.write_docx
    monkeypatch.setattr(docx_io, "write_docx",
                        lambda blocks, path: called.setdefault("blocks", blocks) or real_write(blocks, path))

    docx_io.pdf_to_docx(pdf, out)

    assert called["blocks"] == sentinel
    assert os.path.exists(out)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_docx_io.py::test_pdf_to_docx_scanned_falls_back_to_block_pipeline -v`
Expected: FAIL — `_pdf_has_text_layer` does not exist (`AttributeError` on the `monkeypatch.setattr`).

- [ ] **Step 3: Implement the text-layer probe and the branch**

In `core/docx_io.py`, add the probe and update `pdf_to_docx`:

```python
def _pdf_has_text_layer(pdf_path: str) -> bool:
    """True if any page yields extractable words. A scanned/image-only PDF
    returns False and is routed through OCR instead of pdf2docx."""
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            if page.extract_words():
                return True
    return False


def pdf_to_docx(pdf_path: str, docx_path: str) -> None:
    """Convert a PDF to DOCX preserving page layout via pdf2docx. A scanned PDF
    with no text layer has no layout to preserve — route it through the existing
    OCR block pipeline so the DOCX at least carries searchable text."""
    if not _pdf_has_text_layer(pdf_path):
        from core import pdf_io
        write_docx(pdf_io.read_pdf(pdf_path), docx_path)
        return

    from pdf2docx import Converter

    cv = Converter(pdf_path)
    try:
        cv.convert(docx_path)
    finally:
        cv.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_docx_io.py::test_pdf_to_docx_scanned_falls_back_to_block_pipeline -v`
Expected: PASS.

- [ ] **Step 5: Verify the Task 1 test still passes (real text-layer PDF takes the pdf2docx branch)**

Run: `python -m pytest tests/test_docx_io.py -v`
Expected: both `pdf_to_docx` tests green.

- [ ] **Step 6: Full suite**

Run: `python -m pytest tests/ -v`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add core/docx_io.py tests/test_docx_io.py
git commit -m "feat: pdf_to_docx falls back to OCR block pipeline for scanned PDFs"
```

---

### Task 3: Direct-route table in `dispatch.py`

**Files:**
- Modify: `core/dispatch.py`
- Test: `tests/test_dispatch.py`

**Interfaces:**
- Consumes: `docx_io.pdf_to_docx(source_path, target_path) -> None` from Tasks 1–2.
- Produces: `dispatch.convert` routes `(pdf, docx)` through `_DIRECT_ROUTES` and every other pair through the unchanged `_READERS`/`_WRITERS` block pipeline. New module-level dict `_DIRECT_ROUTES: dict[tuple[str, str], Callable[[str, str], None]]`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dispatch.py` (create the file if absent — check first with `ls tests/`):

```python
from core import dispatch


def test_pdf_to_docx_uses_direct_route(tmp_path, monkeypatch):
    src = str(tmp_path / "a.pdf")
    open(src, "wb").write(b"%PDF-1.4\n%%EOF\n")

    calls = {"direct": 0, "reader": 0}
    monkeypatch.setitem(dispatch._DIRECT_ROUTES, ("pdf", "docx"),
                        lambda s, t: calls.__setitem__("direct", calls["direct"] + 1))
    monkeypatch.setitem(dispatch._READERS, "pdf",
                        lambda p: calls.__setitem__("reader", calls["reader"] + 1) or [("text", "x")])

    out = dispatch.convert(src, "docx")

    assert out == str(tmp_path / "a.docx")
    assert calls == {"direct": 1, "reader": 0}


def test_pdf_to_xlsx_still_uses_block_pipeline(tmp_path, monkeypatch):
    src = str(tmp_path / "a.pdf")
    open(src, "wb").write(b"%PDF-1.4\n%%EOF\n")

    seen = {}
    monkeypatch.setitem(dispatch._READERS, "pdf", lambda p: [("table", [["1"]])])
    monkeypatch.setitem(dispatch._WRITERS, "xlsx",
                        lambda blocks, path: seen.setdefault("blocks", blocks))

    dispatch.convert(src, "xlsx")

    assert seen["blocks"] == [("table", [["1"]])]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dispatch.py -v`
Expected: `test_pdf_to_docx_uses_direct_route` FAILs — `dispatch` has no `_DIRECT_ROUTES`. (`test_pdf_to_xlsx_still_uses_block_pipeline` may already pass — that's fine, it's a regression guard.)

- [ ] **Step 3: Implement the direct-route table**

In `core/dispatch.py`, add the import and the table, and the check inside `convert`:

```python
from core import pdf_io, xlsx_io, docx_io, csv_io

# ... existing SUPPORTED_EXTS, ext_of, _READERS, _WRITERS ...

# Pairs where a faithful conversion cannot go through the (text, table) Block
# model — handed straight to a specialist that reads the source and writes the
# target itself. Checked before the generic reader/writer pipeline.
_DIRECT_ROUTES = {
    ("pdf", "docx"): docx_io.pdf_to_docx,   # (source_path, target_path) -> None
}
```

Then in `convert`, immediately after the two `if ... not in SUPPORTED_EXTS` validation blocks and before `blocks = _READERS[source_ext](source_path)`:

```python
    route = _DIRECT_ROUTES.get((source_ext, target_ext))
    if route:
        target_path = output_path_for(source_path, target_ext)
        route(source_path, target_path)
        return target_path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dispatch.py -v`
Expected: both PASS.

- [ ] **Step 5: Full suite**

Run: `python -m pytest tests/ -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add core/dispatch.py tests/test_dispatch.py
git commit -m "feat: direct-route table in dispatch — pdf->docx bypasses the block pipeline"
```

---

### Task 4: `_reconstruct_financial_table` returns the text it did not turn into rows

**Files:**
- Modify: `core/pdf_io.py` (`_reconstruct_financial_table`, around lines 770–827)
- Test: `tests/test_pdf_io.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `_reconstruct_financial_table(lines: List[str])` now returns a **3-tuple** `(table, preamble, extra)`:
  - `table: Optional[List[List[str]]]` — unchanged meaning.
  - `preamble: Optional[str]` — unchanged meaning (lines before the first transaction anchor).
  - `extra: Optional[str]` — newline-joined lines that appeared **after the last transaction anchor** and carried no amount of their own (page footers, closing-balance notes). `None` when there are none.
  - On the early `return None, None` paths, return `None, None, None`.

  Caveat to encode in a test: a genuine wrapped continuation of the **last** transaction's description that carries no amount also lands in `extra` (it can't be told apart from a footer without document-specific phrase matching). It is still preserved — below the table instead of in the last cell. Earlier rows are unaffected.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pdf_io.py`:

```python
from core.pdf_io import _reconstruct_financial_table


def test_financial_table_returns_trailing_non_amount_lines_as_extra():
    lines = [
        "Kontoauszug 03/2026",
        "01.03.2026 Gutschrift Miete 1.200,00",
        "15.03.2026 Lastschrift Strom -85,40",
        "Seite 1 von 1",
        "Erstellt am 31.03.2026",
    ]
    table, preamble, extra = _reconstruct_financial_table(lines)

    assert table is not None
    assert preamble == "Kontoauszug 03/2026"
    assert extra == "Seite 1 von 1\nErstellt am 31.03.2026"
    # trailing lines must NOT have been folded into the last row's Description
    assert "Seite 1 von 1" not in table[-1][-1]


def test_financial_table_early_return_is_three_none():
    assert _reconstruct_financial_table(["nothing here", "no anchors"]) == (None, None, None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_pdf_io.py -k financial_table -v`
Expected: FAIL — `_reconstruct_financial_table` returns a 2-tuple (`ValueError: not enough values to unpack`).

- [ ] **Step 3: Implement**

In `_reconstruct_financial_table`, replace the loop body's trailing-line handling and the return statements. The loop currently appends every post-anchor non-anchor line to `current["text_parts"]`. Keep that for lines that are followed by another anchor (real wrapped descriptions), but hold the run of trailing non-anchor lines separately and only commit them to `extra` at the end:

```python
    preamble_parts: List[str] = []
    trailing_parts: List[str] = []      # non-amount lines after the last anchor
    rows: List[dict] = []
    current: Optional[dict] = None

    for line_text in lines:
        amounts = _extract_amounts(line_text)
        date_match = _DATE_RE.search(line_text)
        if amounts and date_match:
            # a new anchor means anything we were holding as "trailing" actually
            # belonged to the previous transaction's description after all
            if current is not None and trailing_parts:
                current["text_parts"].extend(trailing_parts)
            trailing_parts = []
            if current:
                rows.append(current)
            current = {
                "date": date_match.group(),
                "amounts": amounts,
                "iban": _find_iban(line_text),
                "text_parts": [line_text],
            }
        elif current is not None:
            trailing_parts.append(line_text)
            if not current["iban"]:
                current["iban"] = _find_iban(line_text)
        else:
            preamble_parts.append(line_text)

    if current:
        rows.append(current)
    if len(rows) < 2:
        return None, None, None

    # ... existing max_amounts / header / table-building loop, unchanged ...

    preamble = "\n".join(preamble_parts) if preamble_parts else None
    extra = "\n".join(trailing_parts) if trailing_parts else None
    return table, preamble, extra
```

Note: the `if not current["iban"]: current["iban"] = _find_iban(line_text)` line is kept in the `elif` branch so an IBAN printed in a footer is still attached to the last row (financial data, not layout).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pdf_io.py -k financial_table -v`
Expected: PASS.

- [ ] **Step 5: Run the whole pdf_io test module — expect callers to break**

Run: `python -m pytest tests/test_pdf_io.py -v`
Expected: failures in tests that call `read_pdf` (because `flush_pending` still unpacks a 2-tuple from this function). That is fixed in Task 6. If any test calls `_reconstruct_financial_table` directly and is not updated, update it now to expect the 3-tuple.

- [ ] **Step 6: Commit**

```bash
git add core/pdf_io.py tests/test_pdf_io.py
git commit -m "feat: _reconstruct_financial_table returns trailing non-row text as a third value"
```

---

### Task 5: `_reconstruct_columned_table` returns the text it did not turn into rows

**Files:**
- Modify: `core/pdf_io.py` (`_reconstruct_columned_table`, lines 448–767)
- Test: `tests/test_pdf_io.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `_reconstruct_columned_table(lines)` now returns a **3-tuple** `(table, preamble, extra)` with the same meanings as Task 4. `extra` = newline-joined non-row physical lines seen **after the last row started** (repeated page furniture after the final transaction, closing summary lines) that are not themselves recognized as a row start. On every `return None, None` path, return `None, None, None`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pdf_io.py`. Reuse whatever word-dict fixture helper the existing tests in this module already use (search the file for `def _w(` / `"x0"` to find it). Sketch, adapt to the local helper:

```python
from core.pdf_io import _reconstruct_columned_table


def test_columned_table_returns_trailing_furniture_as_extra(columned_lines_with_footer):
    # fixture: header row "Datum ... Betrag", two transaction rows,
    # then a non-row line "Summe Auszug 2026 EUR 0,00" and "Seite 1/1"
    table, preamble, extra = _reconstruct_columned_table(columned_lines_with_footer)

    assert table is not None and len(table) >= 3          # header + 2 rows
    assert "Seite 1/1" in (extra or "")
    assert all("Seite 1/1" not in cell for row in table for cell in row)
```

If building a full realistic fixture is heavy, instead add the assertion to an existing columned-reconstruction test that already has trailing lines, and assert the new third return value.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pdf_io.py -k columned_table -v`
Expected: FAIL — 2-tuple unpack error, or `extra` not present.

- [ ] **Step 3: Implement**

In `_reconstruct_columned_table`:

1. Add `trailing_parts: List[str] = []` next to `preamble_parts` (around line 514).
2. In the main `for words in lines:` loop, there is already logic that, once `rows` is non-empty and a line is **not** a new row start and **not** header/preamble/page-number furniture, currently either folds it into the open row or discards it after a page break. Add: when `rows` is non-empty and the line is not a new row start and not being appended to an open row's own columns, append its `_line_text(words)` to `trailing_parts`. When a genuine new row start is then encountered, `trailing_parts.clear()` (those held lines belonged to the row that was open, leave them where the existing code already put them — only the run that survives to the end of the loop is real trailing text).
3. Change both `return None, None` statements (no header / <2 rows / failed sanity gates at lines ~465, ~483, ~756, ~758) to `return None, None, None`.
4. Change the final `return table, preamble` (line ~767) to:

```python
    extra = "\n".join(trailing_parts) if trailing_parts else None
    return table, preamble, extra
```

Keep the guard from Task 4's reasoning: do not let a line that carries an amount in its own amount-column bucket go to `trailing_parts` — a standalone total/balance line must not silently disappear from a place the reader can reconcile. If it has an amount, leave the existing behaviour (folded into the open row) untouched; only amount-free furniture goes to `trailing_parts`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pdf_io.py -k columned_table -v`
Expected: PASS.

- [ ] **Step 5: Full pdf_io module**

Run: `python -m pytest tests/test_pdf_io.py -v`
Expected: direct-call tests green; `read_pdf` tests still red until Task 6. Update any test that calls `_reconstruct_columned_table` directly to expect the 3-tuple.

- [ ] **Step 6: Commit**

```bash
git add core/pdf_io.py tests/test_pdf_io.py
git commit -m "feat: _reconstruct_columned_table returns trailing non-row text as a third value"
```

---

### Task 6: `flush_pending` — table first, then one text block of everything around it

**Files:**
- Modify: `core/pdf_io.py` (`read_pdf` / `flush_pending`, lines 830–890)
- Test: `tests/test_pdf_io.py`

**Interfaces:**
- Consumes: `_reconstruct_columned_table` and `_reconstruct_financial_table`, both now returning `(table, preamble, extra)` (Tasks 4–5).
- Produces: for a borderless statement, `read_pdf` emits `("table", recon_table)` **followed by** a single `("text", context)` block where `context` = `preamble` and `extra` joined with a blank line (either may be empty; the block is emitted only if `context` is non-empty). The old behaviour of emitting `("text", preamble)` *before* the table is removed. The plain-text last-resort fallback (no table at all) is unchanged.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pdf_io.py`. Use the existing PDF-building test helper in the module (search for how other `read_pdf` tests construct a fixture PDF — reportlab or a pdfplumber monkeypatch). Assertion intent:

```python
def test_read_pdf_places_table_first_then_context_block(borderless_statement_pdf):
    # fixture PDF: holder/IBAN/period lines, a headered transaction table,
    # then a "Seite 1 von 1" footer line
    blocks = read_pdf(borderless_statement_pdf)

    kinds = [k for k, _ in blocks]
    assert kinds == ["table", "text"]            # table BEFORE text
    context = blocks[1][1]
    assert "IBAN" in context                     # preamble preserved
    assert "Seite 1 von 1" in context            # trailing preserved
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pdf_io.py -k places_table_first -v`
Expected: FAIL — current order is `["text", "table"]`, and/or unpack error from the 2-tuple call sites.

- [ ] **Step 3: Implement**

In `flush_pending` (lines ~837–857), replace the body:

```python
    def flush_pending() -> None:
        if not pending_lines:
            return
        recon_table, preamble, extra = _reconstruct_columned_table(pending_lines)
        if not recon_table:
            recon_table, preamble, extra = _reconstruct_financial_table(
                [_line_text(words) for words in pending_lines if words is not _PAGE_BREAK]
            )
        if recon_table:
            blocks.append(("table", recon_table))
            context = "\n\n".join(p for p in (preamble, extra) if p)
            if context:
                blocks.append(("text", context))
        else:
            blocks.append((
                "text",
                "\n".join(_line_text(words) for words in pending_lines if words is not _PAGE_BREAK),
            ))
        pending_lines.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pdf_io.py -k places_table_first -v`
Expected: PASS.

- [ ] **Step 5: Full suite — update the other `read_pdf` tests**

Run: `python -m pytest tests/ -v`
Expected: some existing `read_pdf` tests fail because they asserted a leading `("text", preamble)` block or a specific block index/order. Update each to the new contract: table block first, optional single context text block after. Do **not** weaken an assertion that checks a specific number survived into the table — only adjust block ordering/indexing expectations. Re-run until green.

- [ ] **Step 6: Regression check — the merged-total-line bug must stay fixed**

Run: `python -m pytest tests/test_pdf_io.py -k "orphan or total or footer or balance" -v`
Expected: PASS. These guard the HANDOFF-documented bug where a standalone balance/total line must not be merged into a transaction row. Task 5's "amount-free only" guard preserves this; confirm.

- [ ] **Step 7: Commit**

```bash
git add core/pdf_io.py tests/test_pdf_io.py
git commit -m "feat: read_pdf emits the reconstructed table first, then one context text block"
```

---

### Task 7: Update README and HANDOFF

**Files:**
- Modify: `README.md`
- Modify: `HANDOFF.md`

**Interfaces:**
- Consumes: the behaviour delivered by Tasks 1–6.
- Produces: docs only. No code, no tests.

- [ ] **Step 1: README — scope line and dependency note**

In `README.md`, change the opening scope sentence from content-fidelity-only to:

> Batch-converts between PDF, XLSX, DOCX, CSV. Content-fidelity (text + tables) by default. **PDF → DOCX preserves the source page layout** (fonts, text position, tables, images) via `pdf2docx`; a scanned PDF with no text layer is converted through OCR to searchable text with no layout. **PDF → XLSX** places the reconstructed transaction table first, then appends every non-row line found around it (holder, IBAN, period, balances, footers) as plain rows below.

In the setup section, add after the Tesseract note:

> `pip install -r requirements.txt` also installs `pdf2docx` (and its dependency **PyMuPDF**, which is **AGPL-licensed** — fine for internal use, revisit before any commercial redistribution).

Add to Known limitations:

> - Scanned PDF → DOCX carries OCR text only, with no layout (a scan has no text layout to preserve).
> - `pdf2docx` layout fidelity on very complex multi-column or heavily graphical PDFs is good but not exact — verify by eye for anything that matters.
> - PDF → XLSX context text is flat rows in reading order below the table, not a positioned copy. A wrapped continuation of the *last* transaction's description may appear in that block instead of the last cell.

- [ ] **Step 2: HANDOFF — new mechanism and dependency**

In `HANDOFF.md`, under the architecture section, add:

> ### Direct-route conversions (`core/dispatch.py`)
>
> `_DIRECT_ROUTES` maps a `(source_ext, target_ext)` pair to a function that reads the
> source and writes the target itself, bypassing the `(text, table)` Block model. Checked
> before `_READERS`/`_WRITERS` in `convert()`. Currently one entry: `("pdf", "docx") ->
> docx_io.pdf_to_docx`, which uses `pdf2docx` for text-layer PDFs and falls back to
> `pdf_io.read_pdf` + `write_docx` (the existing OCR path) when `_pdf_has_text_layer` is
> False. New dependency `pdf2docx` pulls **PyMuPDF / AGPL** — noted in README, acceptable
> for internal use only.
>
> ### PDF → XLSX context text
>
> Both borderless reconstructors return `(table, preamble, extra)`. `flush_pending` emits
> the `("table", ...)` block first, then a single `("text", ...)` block joining `preamble`
> (pre-table furniture) and `extra` (amount-free lines after the last row). `extra` is
> guarded to never absorb a line that carries an amount in its own bucket — that guard is
> what keeps the documented standalone-balance-line bug fixed.

Update the "Known limitations" / "State as of last session" text to match (the pixel-perfect disclaimer is now qualified for PDF→DOCX).

- [ ] **Step 3: Sanity-check the docs build / render**

Run: `python -m pytest tests/ -v` (unchanged — confirms nothing was accidentally edited in code) and eyeball both markdown files.
Expected: suite green; docs read correctly.

- [ ] **Step 4: Commit**

```bash
git add README.md HANDOFF.md
git commit -m "docs: PDF->DOCX layout preservation, PDF->XLSX context text, pdf2docx/PyMuPDF note"
```

---

## Manual verification (after all tasks — per HANDOFF "Verifying changes")

Not a task; run before telling the user it's done.

1. **PDF → DOCX, text-layer:** convert 3–4 real statements from `..\Test converter` (e.g. `261_ME_RaiBa.pdf`, `Qonto DE90 KA 03_2025 - uradjeno.pdf`, `Spring - Opex - LBBW - 01_04_2026 bis 30_04_2026.pdf`). Open each `.docx` in Word next to the PDF; check columns, fonts, and page structure line up. Note drift, don't fix cosmetically.
2. **PDF → DOCX, scanned:** convert `10300 (P290) bank statement 1.2025.pdf` (scanned). Confirm the `.docx` opens and carries OCR'd text (no crash, no empty file).
3. **PDF → XLSX:** convert the same text-layer statements. Confirm the transaction table is on top and holder / IBAN / period / opening+closing balance / page footer text all appear as rows directly below it, nothing silently missing.
4. `python -m pytest tests/ -v` — full green, count went up from 65.

---

## Self-Review

**Spec coverage:**
- PDF→DOCX layout preservation → Tasks 1, 3. ✓
- Scanned-PDF fallback → Task 2. ✓
- `dispatch` direct-route table → Task 3. ✓
- PDF→XLSX keep surrounding text, table first → Tasks 4, 5, 6. ✓
- `pdf2docx` dependency + AGPL/PyMuPDF note → Task 1 (dep), Task 7 (note). ✓
- README + HANDOFF updates → Task 7. ✓
- Testing strategy (smoke + content for docx, fixtures for pdf_io, manual side-by-side) → per-task tests + Manual verification section. ✓
- Error handling (propagate to `batch.run_batch`) → no code needed; `convert` lets exceptions propagate, existing `batch` catches. Called out in spec, no task required.

**Placeholder scan:** Task 5's test fixture is described as "reuse the module's existing helper / adapt" rather than fully spelled out — this is because the existing `tests/test_pdf_io.py` helper shape is not visible from the spec and must be matched to what's there. The assertion intent and the fixture contents (header row, 2 rows, 2 named footer lines) are concrete. Acceptable; flagged for the executor to wire to the local helper. No other placeholders.

**Type consistency:** `pdf_to_docx(pdf_path, docx_path) -> None` used identically in Tasks 1, 2, 3. `_DIRECT_ROUTES` value signature `(source_path, target_path) -> None` matches. Both reconstructors return `(table, preamble, extra)` — 3-tuple defined in Task 4, mirrored in Task 5, consumed in Task 6. `_pdf_has_text_layer(pdf_path) -> bool` defined and used in Task 2. Consistent.
