from batch import scan_folder, run_batch, find_collisions
from core.csv_io import write_csv
from core.dispatch import output_path_for


def test_scan_folder_finds_only_supported_files(tmp_path):
    write_csv([("table", [["a"]])], str(tmp_path / "a.csv"))
    (tmp_path / "b.txt").write_text("ignore me")
    (tmp_path / "sub").mkdir()
    write_csv([("table", [["x"]])], str(tmp_path / "sub" / "c.csv"))  # not scanned, subfolder

    result = scan_folder(str(tmp_path))

    assert result == [str(tmp_path / "a.csv")]


def test_run_batch_skips_same_format(tmp_path):
    p = tmp_path / "in.csv"
    write_csv([("table", [["a"]])], str(p))
    updates = []

    run_batch([str(p)], "csv", lambda path, status: updates.append((path, status)))

    assert updates == [(str(p), "skipped (already csv)")]


def test_run_batch_converts_and_reports_output(tmp_path):
    p = tmp_path / "in.csv"
    write_csv([("table", [["a"]])], str(p))
    updates = []

    run_batch([str(p)], "xlsx", lambda path, status: updates.append((path, status)))

    assert len(updates) == 1
    path, status = updates[0]
    assert path == str(p)
    assert status.startswith("done -> ")
    assert status.endswith(".xlsx")


def test_run_batch_reports_error_without_stopping(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("")  # empty file, valid CSV (zero rows) — force real error via unsupported ext instead
    good = tmp_path / "good.csv"
    write_csv([("table", [["a"]])], str(good))
    updates = []

    # simulate an error by pointing at a nonexistent-but-supported-ext file
    missing = str(tmp_path / "missing.pdf")
    run_batch([missing, str(good)], "xlsx", lambda path, status: updates.append((path, status)))

    assert updates[0][0] == missing
    assert updates[0][1].startswith("error: ")
    assert updates[1][1].startswith("done -> ")


def test_find_collisions_detects_shared_basename(tmp_path):
    csv_path = str(tmp_path / "data.csv")
    xlsx_path = str(tmp_path / "data.xlsx")

    collisions = find_collisions([csv_path, xlsx_path], "docx")

    assert collisions == [(csv_path, xlsx_path, output_path_for(csv_path, "docx"))]


def test_find_collisions_none_for_distinct_basenames(tmp_path):
    a = str(tmp_path / "alpha.csv")
    b = str(tmp_path / "beta.xlsx")

    collisions = find_collisions([a, b], "docx")

    assert collisions == []


def test_find_collisions_ignores_files_already_in_target_format(tmp_path):
    # a "data.docx" already queued won't be converted (run_batch skips same-format
    # files), so it can't collide with anything even if the basename matches.
    docx_path = str(tmp_path / "data.docx")
    csv_path = str(tmp_path / "data.csv")

    collisions = find_collisions([docx_path, csv_path], "docx")

    assert collisions == []


def test_find_collisions_real_world_overwrite_reproduces_without_check(tmp_path):
    # Demonstrates the underlying bug this guards against: converting data.csv and
    # data.xlsx to docx in the same batch silently makes the second overwrite the
    # first, and both rows report "done".
    csv_path = tmp_path / "data.csv"
    xlsx_path = tmp_path / "data.xlsx"
    write_csv([("table", [["from", "csv"]])], str(csv_path))
    from core.xlsx_io import write_xlsx
    write_xlsx([("table", [["from", "xlsx"]])], str(xlsx_path))

    collisions = find_collisions([str(csv_path), str(xlsx_path)], "docx")
    assert len(collisions) == 1  # caught before the batch runs

    # Without the guard, running the batch anyway proves the collision is real:
    updates = []
    run_batch([str(csv_path), str(xlsx_path)], "docx", lambda p, s: updates.append((p, s)))
    assert all(status.startswith("done ->") for _, status in updates)

    from core.docx_io import read_docx
    final = read_docx(str(tmp_path / "data.docx"))
    # Only one of the two sources survived — whichever ran second clobbered the first.
    assert final == [("table", [["from", "xlsx"]])]
