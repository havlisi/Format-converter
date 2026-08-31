# Handoff notes — Format Converter

Context for picking this project back up without re-deriving everything. Written 2026-08-25,
heavily updated 2026-08-27 after a long session of real-file bug hunting and a GUI rebuild.

## What this is

Batch converter between PDF, XLSX, DOCX, CSV. Desktop GUI via **pywebview** — `python app.py`
loads `ui/index.html` (a dark, glass-styled page: blurred gradient background, translucent
cards, pill buttons) in a native window. `Api` in `app.py` bridges JS calls to the existing
`batch.py` logic (`add_files`/`add_folder`/`check_conflicts`/`run_conversion`), all unchanged
from the previous Tkinter app. Core logic in `core/` (one reader/writer module per format),
dispatched via `core/dispatch.py`.

Repo: https://github.com/havlisi/Format-converter (pushed via `git subtree split --prefix=converter`
from the monorepo at `C:\Users\Isidora\Isis\claude` — that repo mixes in an unrelated project,
so **never** push its `master` directly). **The push workflow has a real gotcha now — read
"Pushing updates to GitHub" below before pushing, not after it fails.**

Financial accuracy is the top priority the user cares about; when in doubt, code prefers to
fall back to safe, unstructured plain text over shipping a wrong or misattributed number. This
showed up repeatedly: several real bugs this session were "confidently wrong structured data"
rather than crashes, which is the worse failure mode and the one to keep hunting for.

## Giving a copy to a colleague (clean Windows machine, step by step)

Written for a non-developer following it verbatim. Everything is free; no admin rights needed
beyond installing Python.

1. **Install Python.** Go to <https://www.python.org/downloads/>, click the yellow "Download
   Python 3.x" button, run the installer. On the first installer screen **tick "Add python.exe
   to PATH"** before clicking "Install Now" — skipping this is the single most common thing that
   breaks step 5.

2. **Make a GitHub account.** Go to <https://github.com/signup>, pick a username, confirm the
   email. Free tier is all that's needed. Then tell the repo owner (Isidora) that username so she
   can add it under the repo's **Settings → Collaborators** — needed only if the repo is private;
   skip if it's public (it currently is). Either way, having the account is what makes GitHub
   Desktop's sign-in work.

3. **Install GitHub Desktop and clone the repo.**
   - Download from <https://desktop.github.com>, run the installer.
   - Open it, **"Sign in to GitHub.com"**, log in with the account from step 2, authorize in the
     browser when it asks.
   - **File → Clone repository… → URL tab.** In the URL field paste
     `https://github.com/havlisi/Format-converter`. In "Local path" pick where the folder lives
     (e.g. `C:\Users\<name>\Converter app` — this exact path is what `HANDOFF.md`'s push section
     already assumes for the deployed copy). Click **Clone**.
   - GitHub Desktop now shows the repo. **"Repository → Show in Explorer"** opens the folder on
     disk — that folder directly contains `app.py` and `requirements.txt`.

   **Getting updates later:** open GitHub Desktop, make sure "Current repository" is
   Format-converter, click **"Fetch origin"**, then **"Pull origin"** if it offers it. That
   pulls the latest code. Re-run `pip install -r requirements.txt` after a pull only if
   `requirements.txt` changed (GitHub Desktop's history view shows what changed).

4. **Open a terminal *inside the project folder*.** This matters — every command below only
   works from the folder that directly contains `app.py` and `requirements.txt`, not its parent
   and not Downloads. In GitHub Desktop: **Repository → Show in Explorer**. In the Explorer
   window that opens, click the address bar (the white strip showing the path), type
   `powershell`, press Enter. A blue window opens, already pointed at the right folder. Confirm
   it with:

       dir

   The list must include `app.py`, `requirements.txt`, `batch.py`, `core`, `ui`. If it doesn't,
   you're in the wrong folder — see "`requirements.txt` not found" in Troubleshooting below.

5. **Install the libraries the app needs.** In that same window, run:

       python -m pip install -r requirements.txt

   Wait for it to finish (a minute or two, lots of scrolling text — that's normal). `python -m
   pip` (not bare `pip`) guarantees it installs for the same Python that runs the app. If it
   says `python is not recognized`, Python wasn't added to PATH in step 1 — reinstall Python and
   tick that box.

6. **(Only if she'll convert *scanned* PDFs.)** A scanned PDF is a photo/scan with no selectable
   text. Those need Tesseract OCR, installed separately:

       winget install UB-Mannheim.TesseractOCR

   Skip this if she's only converting normal PDFs, Word, Excel, or CSV — those work without it.
   (A scanned PDF without Tesseract fails with a clear message telling her to install it; it
   never crashes.)

7. **Run the app.**

       python app.py

   A window titled "Format Converter" opens. (It uses the Edge **WebView2** runtime, which ships
   with Windows 10/11 by default — if the window is blank, install "Evergreen WebView2 Runtime"
   from Microsoft and rerun.)

   To start it again next time: repeat step 4 (open `powershell` in the folder) and run
   `python app.py`. That's the whole launch — there's no installer or Start-menu shortcut unless
   she makes one.

### Using the converter window

1. **Add Files…** — pick one or more files, or **Add Folder…** to queue every supported file in
   a folder. **Clear** empties the queue. Supported: PDF, XLSX, DOCX, CSV.
2. **Convert to** — pick the target format from the dropdown.
3. **Convert All** — each file is written *next to the original*, same name, new extension
   (`statement.pdf` → `statement.xlsx`). Per-file status shows in the list; a red warning
   appears first if two queued files would overwrite the same output or if an output already
   exists.
4. Financial data caveat to pass along: for anything money-related, **spot-check the numbers
   against the source**, especially from scanned PDFs. Words the OCR itself flagged as
   uncertain are wrapped in `¿...?` in the output so they're easy to find.

### Troubleshooting a colleague's setup

Almost every "it doesn't work" here is the terminal not being in the project folder, or `pip`
and `python` being two different installs. In order:

- **`requirements.txt` not found / `No such file or directory`** — the terminal isn't in the project
  folder. Run `dir`; if you don't see `app.py` and `requirements.txt`, you're in the wrong
  place. Fix: GitHub Desktop → **Repository → Show in Explorer**, then address bar → `powershell`
  → Enter. Or search for it: `Get-ChildItem -Path $HOME -Recurse -Filter requirements.txt
  -ErrorAction SilentlyContinue | Select-Object FullName`. Watch for a doubled folder like
  `Format-converter\Format-converter` (or `...-main\...-main` from a ZIP) — the real one is the
  inner folder that contains `app.py`.
- **`No module named 'webview'`** (the pip name is `pywebview`, the import name is `webview` —
  that mismatch is normal) — the libraries were installed for a different Python. Reinstall with
  `python -m pip install -r requirements.txt` (note the `python -m` prefix), then
  `python -m pip show pywebview` should print a Version and Location. If `where.exe python`
  lists more than one path, or a path under `WindowsApps`, that's the Microsoft Store stub —
  install real Python from python.org with "Add to PATH" ticked, reopen PowerShell, reinstall.
- **`python` / `pip` is not recognized** — Python isn't on PATH. Reinstall from python.org and
  tick "Add python.exe to PATH" on the first installer screen.
- **The window opens but is blank / white** — missing WebView2 runtime. Install "Evergreen
  Standalone WebView2 Runtime" from Microsoft's site and rerun `python app.py`. (Rare on
  Win10/11, which bundle it.)
- **A scanned PDF errors out** mentioning Tesseract — that's step 6; run
  `winget install UB-Mannheim.TesseractOCR`, then reopen PowerShell so PATH refreshes.

## The GUI (`app.py`, `ui/index.html`)

Rebuilt from Tkinter to pywebview this session for a modern look (the user showed a reference
glassmorphism mockup — real backdrop-blur/translucency is impossible in plain Tkinter, so the
whole presentation layer was swapped; `batch.py`/`core/` untouched). New dependency: `pywebview`
(in `requirements.txt`; uses the system's Edge WebView2 runtime on Windows, present by default
on Win10/11).

**A real, now-fixed bug worth knowing about if this file is touched again:** `Api` must never
store the pywebview `Window` object (or anything reachable from it) as a *public* attribute.
pywebview builds its JS-callable function list by walking every public attribute of the
`js_api` object with `dir()`/`getattr()`, recursing into anything non-callable. A plain
`self.window = window` sent that walk straight into the native WinForms window object, then
into raw .NET COM properties (`window.native.AccessibilityObject.Bounds...`), which cycles back
on itself indefinitely (`Rectangle.Empty` exposes its own `.Empty`, forever) — froze the window
on every launch. Fixed by naming it `self._window` (pywebview explicitly skips underscore-
prefixed attributes in that walk). An earlier, wrong diagnosis (raising Python's recursion
limit) only changed the odds of the walk finishing before hanging — don't reintroduce a public
non-callable attribute on `Api` without checking this.

Verify a GUI change with a **scripted** launch-and-poll, not just "did a window appear once":
launch `python app.py` in the background, poll `Get-Process python | Select Responding` every
1-2s for at least 15-20s across 2-3 separate launches. A single lucky run can hide a real
intermittent freeze (this is exactly how the bug above stayed hidden through one round of
testing). A full-screen screenshot tool was tried for visual verification and abandoned — it
captured unrelated desktop content, not the app window; don't rely on it here.

## PDF → table reconstruction architecture (`core/pdf_io.py`)

Three layers, tried in order, each falling back to the next on failure:

1. **`good_tables`** — pdfplumber's own `find_tables()`, used as-is when it finds a real
   grid-lined table that isn't degenerate (`_is_degenerate_table`).
2. **`_reconstruct_columned_table`** — the primary path for borderless statements. Finds the
   document's own header row, clusters header words into columns by x-gap
   (`_COLUMN_GAP_THRESHOLD = 6.0`), buckets every word by x-position into those columns, and
   groups physical lines into rows via `_ROW_START_DATE_RE`. Has a **sanity gate** (>=90% of
   rows must yield valid dates/amounts) — if it can't be satisfied, returns `None` and the
   caller falls back to step 3.
3. **`_reconstruct_financial_table`** — generic fallback. Anchors each transaction on a line
   carrying both a date and a currency-tagged amount; everything else folds into one
   "Description" column.
4. If even that fails: raw text, one block, no structure. Still shows the user everything —
   never silently drops content.

### `_is_degenerate_table` — judge by a MAJORITY of columns being sparse, not any one

pdfplumber's table detector occasionally imagines a faint grid in ordinary borderless text and
reports a "table" whose value all but always lands in one column (a 2-column phantom, one
column populated 3-11% of rows — coincidental word alignment, not real data). But a **real**,
fully-headed table can legitimately have one or two optional fields (an "Anhang"/attachment or
"Kommentar"/remarks column, populated on real Aareal Bank statements only once every several
rows) sitting right alongside many consistently-populated columns. Rejecting on any single
sparse column threw real 11-column tables out entirely. Fixed to require a **majority** of
columns sparse (`sparse_cols * 2 >= cols`) — the actual noise tables seen were never more than
2 columns with exactly 1 sparse (50%); a real table with 2 sparse fields among 9 full ones
(18%) is a different, legitimate shape. **Watch for this exact tension again** if the threshold
is ever tightened.

### Header detection — several false-positive/false-negative guards, in order

- `_looks_like_header` rejects a candidate that itself starts with a transaction's own date (a
  transaction line whose own text coincidentally carries both a date and amount keyword — e.g.
  a "Wert:" note plus "Gutschrift" — must not be mistaken for the header).
- Rejects a candidate clustering into fewer than 3 column groups (a short wrapped fragment can
  coincidentally carry both keywords too).
- **A column whose clustered label matches BOTH a date and an amount keyword** isn't a real
  single-purpose column — it's several adjacent header cells rendered with **zero gap** between
  them, a font-kerning defect seen in real Aareal/LBBW statement PDFs
  ("...BuchungstextBeguenstigterVerwendungszweckBetrag" as one run). Typing it as either would
  silently discard every row's real payee/description/amount. Left untyped instead — full raw
  text survives in one blob, lossy but never a silently vanished amount. **This is also why
  those statements sometimes still show a merged blob for a given page even after the fix
  below**: pdfplumber's own grid-line detection is inconsistent page-to-page within the same
  document — some pages get a clean grid (real columns split correctly), others don't (fall to
  the merged-blob path). The values are still correct either way; only the column split is
  inconsistent. Not further investigated.
- **Amount-only header fallback**: an OCR'd statement's header can be missing *only* the
  date-label word — confirmed on a real scanned Kreissparkasse statement that "Datum" is
  perfectly legible in isolation (cropped and OCR'd alone: reads fine) but Tesseract's
  *whole-page* layout analysis drops it anyway. Neither higher DPI, alternate page-segmentation
  modes (`--psm`), nor removing nearby page noise recovered it in a full-page pass — a genuine
  miss, not a misread worth fuzzy-matching. `_find_header_words` now falls back to an
  amount-only match (same false-positive guards, minus the date-keyword requirement) and
  assumes the first column is the date column — never trusted blindly, gated by the same
  >=90%-valid-dates sanity check plus the fact that row-start detection itself never fires at
  all if column 0 isn't real dates.

### Row-start false positives — a real transaction line is never *just* its date

- The dot-date row-start pattern excludes a page's printed generation timestamp ("21.02.2025
  11:43:32" — a clock time immediately after the date marks a timestamp, not a transaction).
  The slash-date pattern needed the identical guard added (a timestamp like "5/5/2026 6:35 PM"
  was spawning a bogus row on every page of an Aareal statement) — implemented with the same
  explicit-either/or year-matching trick the dot pattern already used, for the same reason: a
  plain optional group lets regex backtracking dodge the lookahead by matching a
  wrong-length year.
- **Bare page-number fractions** ("1/3" — page 1 of 3) read identically to a valid partial date
  (day=1, month=3) and were spawning a bogus row on OCR'd scanned statements. A real transaction
  line is never *just* its own date with nothing else on the physical line; `_BARE_PAGE_NUMBER_RE`
  recognizes and skips an isolated `\d{1,2}/\d{1,3}` line as page furniture before row-start
  detection ever sees it.
- A date **glued directly onto the next word** with no space ("29.12.2023Entgeltabrechnung" —
  one pdfplumber token) used to lose the glued word entirely (bucketed whole into the date
  column, and `_normalize_date` only ever pulls the date substring back out). Now split at the
  date match's end and the remainder routed to the row's first non-date, non-amount column.

### Amount routing — prefer each column's own bucket, never a blind whole-row scan

- **Single/multi amount column**: each amount column's own x-bucketed text is tried first
  (`_parse_first_bare_amount`) — already correctly scoped by position, so correct even when a
  free-text description column earlier in reading order happens to contain its own
  currency-tagged number (a reference amount cited in a "Verwendungszweck" narrative). The
  whole-row scan is only a fallback for genuine right-alignment drift (a value's left edge
  spilling into the previous column's x-range, leaving its own bucket empty).
- **Debit/credit split vs. both-always-present pair (`is_split_pair`)**: decided from each
  column's **own bucket**, not a currency-tagged whole-row scan — a per-row amount often has no
  currency code of its own (the header states it once), so a currency-tagged scan alone can
  miss it and wrongly classify a genuine both-present pair (e.g. "Originalumsatz"/"EUR-Umsatz",
  restating the same figure twice) as a split, silently blanking one column on every row. A real
  split pair never has both columns' own bucket populated on the same row; a both-present pair
  does, on virtually every row.
- **Anchor date column** is read from the fragment captured at the moment the row *started*,
  not re-derived from the bucket's full accumulated text — a repeated page footer restating the
  statement's own date range, glued onto whatever row is still open when a page ends, could
  otherwise plant a later, fuller date match ahead of the row's own real one in
  `_normalize_date`'s fallback chain (reported the statement's start date instead of the
  transaction's).

### Orphan lines before the first row — merge them into it, but only if they carry no amount

A row's own tallest cell (a multi-line description) can render starting *above* that row's own
date/amount baseline — its first physical line then sorts ahead of the row-start line by
vertical position, arriving before any row exists yet. These used to be dumped as document
preamble text and lost from the row entirely. Now held (`pending_orphan_lines`) and prepended to
the row that follows — but **only when the orphan line carries no amount of its own**, checked
directly in its own amount-column bucket (bare-number-tolerant, not a currency-tagged scan — the
same reasoning as the split-pair fix above). A real standalone summary/total line (an opening
balance, a running total) always does carry an amount, and merging one of those into the next
row corrupts that row's own amount with the balance figure instead — this was a real regression
caught while fixing the original issue, now guarded by a dedicated test.

### `write_xlsx` — a raw-text fallback block must be split into rows, not one cell

A "text" block used to be written into a **single cell**. openpyxl silently truncates a cell at
Excel's ~32,767-character limit with no error — an 86-page StarMoney statement's ~102,800-char
raw-text fallback collapsed into one truncated, effectively unreadable cell. Now split on `\n`
into one row per line.

### OCR (`_ocr_page_line_words`)

A page with no text layer but an embedded image gets rendered (pdfplumber's `to_image()`) and
run through `pytesseract.image_to_data`, converting output into the same `{text, x0, x1, top,
bottom}` word-dict shape as pdfplumber's own `extract_words()`. Low-confidence words get wrapped
in `¿...?`. Requires Tesseract installed separately (`winget install UB-Mannheim.TesseractOCR`);
auto-detects the default Windows install path if not yet on PATH.

## Direct-route conversions & surrounding-text handling

### Direct-route conversions (`core/dispatch.py`)

`_DIRECT_ROUTES` maps a `(source_ext, target_ext)` pair to a function that reads the
source and writes the target itself, bypassing the `(text, table)` Block model. Checked
before `_READERS`/`_WRITERS` in `convert()`. Currently one entry: `("pdf", "docx") ->
docx_io.pdf_to_docx`, which uses `pdf2docx` for text-layer PDFs and falls back to
`pdf_io.read_pdf` + `write_docx` (the existing OCR path) when `_pdf_has_text_layer` is
False. New dependency `pdf2docx` pulls **PyMuPDF / AGPL** — noted in README, acceptable
for internal use only.

### PDF → XLSX context text

Both borderless reconstructors return `(table, preamble, extra)`. `flush_pending` emits
the `("table", ...)` block first, then a single `("text", ...)` block joining `preamble`
(pre-table furniture) and `extra` (amount-free lines after the last row). `extra` is
guarded to never absorb a line that carries an amount in its own bucket — that guard is
what keeps the documented standalone-balance-line bug fixed.

## Known limitations (also in README.md — keep both in sync if this changes)

- **OCR is meaningfully less reliable than a real text layer.** Beyond generic digit misreads:
  a header's date-label word can be dropped entirely by Tesseract's whole-page layout analysis
  even when perfectly legible in isolation (see "amount-only header fallback" above — partially
  mitigated, not solved). On at least one real scanned statement, OCR degradation goes deeper
  than the header: several individual transactions' own dates also aren't recognized as
  row-starts, merging multiple real transactions into one row. The sanity gate correctly catches
  this and falls back to safe raw text (no data lost, just unstructured) rather than ship a
  table with silently merged transactions — but the file still isn't structured. Not solved this
  session; would need either a fundamentally different OCR strategy (tiled/region OCR instead of
  whole-page) or per-document tuning.
- **A header split across multiple physical lines** ("Datum" / "Erlaeuterung" / "Betrag EUR" each
  fully on their own OCR line, seen on a real Hilee GmbH statement) isn't recognized at all —
  the amount-only fallback above only handles a *missing* date label, not one whose surviving
  keywords are scattered across separate lines. Would need multi-line header merging; not
  started.
- **Amount rows printed with no debit/credit marker at all**, relying solely on print color
  (red for debit, black for credit) to convey sign — seen on real Aareal/LBBW statements. The
  amount's magnitude is always correct; sign is unrecoverable from text alone without threading
  character-color data through the whole extraction pipeline. Deliberately not attempted this
  session (real cost for a narrow benefit, and a wrong automatic guess is worse than an honest
  unsigned number) — if ever tackled, pdfplumber exposes `non_stroking_color` per character
  (confirmed red ≈ `(1.0, 0.0, 0.0)` vs. black `(0.0, 0.0, 0.0)` on a real file).
- **A repeated page footer can still pollute the *description* of the last row on a page**
  (confirmed on Qonto statements: the footer restates the statement's date range + company name
  + IBAN, glued onto the still-open row's non-date columns — the date fix above stops it from
  corrupting the *date*, but Description/IBAN aren't protected the same way). Cosmetic, not
  financial. Deliberately not fixed — a robust general fix needs document-specific phrase
  matching that's fragile across bank templates.
- **A value that's genuinely present once in the source PDF can appear "duplicated"** in the
  output — once in a free-text description column (because that's literally how the bank
  printed it, e.g. an IBAN inline in "Verwendungszweck") and once more in a dedicated extracted
  column (IBAN, or an amount that also reads inline). This is a real product/design question
  (strip it from the description? leave both?) raised by the user and never resolved — flagged,
  not fixed.
- A source PDF whose own font renders header words with zero gap between them can still produce
  a garbled header *label* even after the fixes above (data below is unaffected — the untyped
  merged-column fallback and the amount-only fallback both handle this at the data level; only
  the header's own display text stays garbled).
- Non-tabular documents (label/value pairs) get date/amount/IBAN extracted but not fully
  column-split.
- **PDF → DOCX preserves page layout** (via `pdf2docx`, direct-route in `dispatch.py`) — the
  "content-fidelity, not pixel-perfect" framing applies to every *other* pair, not this one. A
  *scanned* PDF → DOCX still carries OCR text only with no layout, and `pdf2docx` fidelity on very
  complex multi-column or heavily graphical PDFs is good but not exact — verify by eye.
- **PDF → XLSX** surrounding text (holder / IBAN / period / balances / footers) is appended as flat
  rows in reading order below the table, not positioned. A wrapped continuation of the *last*
  transaction's description may land in that block instead of the last cell.

## Real test files used across sessions (NOT in the repo — personal financial data)

Ask the user to re-share relevant ones if continuing PDF work. Formats covered so far:
Sparkasse (dot dates, Betrag/Saldo), Aareal Bank + LBBW/BW-Bank (PropCo Spring/Diamond — Kaution
and Opex/Miete accounts, font-kerning-merged headers, some amounts with no H/S marker, up to 504
pages), StarMoney/HAASE export (H/S suffix, repeated multi-page header, a 106-page file that
used to fragment into 29 disjointed blocks — now one continuous table), Qonto (slash dates, no
year per row, Belastung/Gutschrift split, international decimal notation), RaiBa (native grid
table, the gold-standard reconciliation test — 1,494 transactions, zero mismatches), a
"Transaction Details" one-per-page US-format report, Hilee GmbH (scanned, multi-line-split
header, unsolved), and a scanned Kreissparkasse/GIEAG statement (P290 — OCR investigation
above).

## Verifying changes to `pdf_io.py`

No committed fixtures replicate the real bank files (privacy), so regression-check by hand
against whichever real files are available. Two complementary methods, both used extensively
this session:

1. **Reconciliation** — for anything with a running balance column, verify
   `Saldo[i] == Saldo[i-1] + Betrag[i]` for every row (direction depends on whether the
   statement lists newest-first or oldest-first — check the printed Start-/Endsaldo against
   your assumed direction before trusting a "0 mismatches" result). A clean chain across
   hundreds or thousands of rows, and a final computed balance matching the document's own
   printed Endsaldo to the cent, is very strong evidence — much stronger than eyeballing.
2. **Visual side-by-side** — render the source PDF page to an image (`page.to_image(resolution=150).save(...)`)
   and view it, then dump the corresponding XLSX rows as text and compare by eye. Caught real
   bugs the reconciliation check alone wouldn't (e.g. a dropped description word, a stray
   preamble block) — and caught cases where the reconciliation script itself was wrong (sign
   convention, direction), not the converter. Don't fully trust one method without the other.

The unit tests (`tests/test_pdf_io.py`) cover synthetic fixtures for every fix above and should
still pass: `python -m pytest tests/ -v` (75 tests as of this session).

## Pushing updates to GitHub

From `C:\Users\Isidora\Isis\claude` (the monorepo root, not `converter/`):

    git branch -D converter-only          # if it already exists locally
    git subtree split --prefix=converter -b converter-only

**Gotcha, learned the hard way this session:** if *anything* has ever been pushed to
`havlisi/Format-converter` outside this exact split-and-push flow (e.g. someone adding a file
directly on GitHub's web UI — happened once, a `pyproject.toml`), a plain
`git push origin converter-only:main` gets rejected as non-fast-forward, **every single time
from then on** — `git subtree split -b` regenerates entirely fresh commit objects on each run
(even `--onto origin/main` doesn't help; this repo's history was never set up with proper
subtree metadata for that to hook into). The fix, repeatable, using an isolated worktree so a
mistaken `git checkout` can never clobber the monorepo's own working tree (a real mistake made
once this session — recovered fine, but avoid repeating it):

    git worktree add "<some-temp-dir>" converter-only
    cd "<some-temp-dir>"
    git merge origin/main --allow-unrelated-histories -m "merge: reconcile with GitHub main"
    git push origin HEAD:main
    cd "C:\Users\Isidora\Isis\claude"
    git worktree remove "<some-temp-dir>" --force

Then sync the deployed copy the user actually runs, at
`C:\Users\Isidora\Isis\Claude apps\Converter app\Format-converter`:

    git pull origin main --ff-only
    python -m pytest tests/ -v   # confirm before telling the user it's live

**Never** `git checkout converter-only` (or any subtree-split branch) directly in the monorepo's
own working tree at `C:\Users\Isidora\Isis\claude` — that branch's tree has files at the
*root* (no `converter/` prefix), so checking it out there replaces the whole monorepo's visible
file layout, mixing an unrelated project's files with the subtree's. Always use a worktree.

`origin` is already set to `https://github.com/havlisi/Format-converter.git`.

## State as of last session

Working tree clean. All real test files on hand convert without crashing; every one with a
verifiable running-balance column reconciles to the printed Endsaldo (RaiBa: 1,494 transactions
zero mismatches; the 4 Aareal/LBBW files: zero *unexplained* mismatches — all traced to the two
documented limitations above). GUI rebuilt to pywebview and verified stable across multiple
scripted launches. 75 tests passing.

This session added layout-preserving **PDF → DOCX** (via `pdf2docx`, wired as a direct route in
`dispatch.py`; a scanned PDF with no text layer falls back to the existing OCR block pipeline) and
changed **PDF → XLSX** to emit the reconstructed transaction table first, then a single text block
carrying the holder / IBAN / period / balance / footer lines that surround it. New dependency
`pdf2docx` (pulls PyMuPDF / AGPL).
