from batch import scan_folder, run_batch
from core.csv_io import write_csv


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
