from openpyxl import Workbook
from core.xlsx_io import read_xlsx, write_xlsx


def test_write_then_read_round_trip(tmp_path):
    p = tmp_path / "out.xlsx"
    blocks = [("table", [["Name", "Age"], ["Bob", "30"]])]

    write_xlsx(blocks, str(p))
    result = read_xlsx(str(p))

    assert result == [("table", [["Name", "Age"], ["Bob", "30"]])]


def test_read_skips_fully_empty_rows(tmp_path):
    p = tmp_path / "in.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["a", "b"])
    ws.append([None, None])
    ws.append(["c", "d"])
    wb.save(p)

    result = read_xlsx(str(p))

    assert result == [("table", [["a", "b"], ["c", "d"]])]


def test_write_text_block_goes_in_column_a(tmp_path):
    p = tmp_path / "out2.xlsx"
    blocks = [("text", "hello"), ("table", [["x"]])]

    write_xlsx(blocks, str(p))
    result = read_xlsx(str(p))

    assert result == [("table", [["hello"], ["x"]])]
