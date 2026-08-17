import csv
from core.csv_io import read_csv, write_csv


def test_read_csv_returns_single_table_block(tmp_path):
    p = tmp_path / "in.csv"
    p.write_text("Name,Age\nBob,30\nAmy,25\n", encoding="utf-8")

    blocks = read_csv(str(p))

    assert blocks == [("table", [["Name", "Age"], ["Bob", "30"], ["Amy", "25"]])]


def test_write_csv_round_trip(tmp_path):
    p = tmp_path / "out.csv"
    blocks = [("table", [["Name", "Age"], ["Bob", "30"]])]

    write_csv(blocks, str(p))

    with open(p, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows == [["Name", "Age"], ["Bob", "30"]]


def test_read_csv_falls_back_to_cp1252_on_decode_error(tmp_path):
    p = tmp_path / "windows.csv"
    # "café" encoded as cp1252 (Windows-1252) — not valid utf-8, so a plain
    # utf-8-sig read would raise UnicodeDecodeError.
    content = "Name,City\r\nBob,caf\xe9\r\n"
    with open(p, "wb") as f:
        f.write(content.encode("cp1252"))

    blocks = read_csv(str(p))

    assert blocks == [("table", [["Name", "City"], ["Bob", "café"]])]


def test_write_csv_separates_consecutive_tables_with_blank_row(tmp_path):
    p = tmp_path / "multi_sheet.csv"
    blocks = [("table", [["Sheet1"]]), ("table", [["Sheet2"]])]

    write_csv(blocks, str(p))

    with open(p, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows == [["Sheet1"], [], ["Sheet2"]]


def test_write_csv_flattens_text_blocks(tmp_path):
    p = tmp_path / "out2.csv"
    blocks = [("text", "hello"), ("table", [["a"]])]

    write_csv(blocks, str(p))

    with open(p, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows == [["hello"], ["a"]]
