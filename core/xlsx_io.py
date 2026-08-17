from openpyxl import Workbook, load_workbook
from core.types import Block
from typing import List


def read_xlsx(path: str) -> List[Block]:
    wb = load_workbook(path, data_only=True)
    blocks: List[Block] = []
    for ws in wb.worksheets:
        rows = []
        for row in ws.iter_rows(values_only=True):
            str_row = ["" if c is None else str(c) for c in row]
            if any(cell != "" for cell in str_row):
                rows.append(str_row)
        if rows:
            blocks.append(("table", rows))
    return blocks


def write_xlsx(blocks: List[Block], path: str) -> None:
    wb = Workbook()
    ws = wb.active
    row_idx = 1
    for kind, content in blocks:
        if kind == "text":
            ws.cell(row=row_idx, column=1, value=content)
            row_idx += 1
        else:
            for row in content:
                for col_idx, val in enumerate(row, start=1):
                    ws.cell(row=row_idx, column=col_idx, value=val)
                row_idx += 1
    wb.save(path)
