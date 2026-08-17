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


def test_write_csv_flattens_text_blocks(tmp_path):
    p = tmp_path / "out2.csv"
    blocks = [("text", "hello"), ("table", [["a"]])]

    write_csv(blocks, str(p))

    with open(p, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows == [["hello"], ["a"]]
