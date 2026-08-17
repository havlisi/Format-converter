from openpyxl import Workbook, load_workbook
from core.types import Block
from typing import List

_FORMULA_PREFIXES = ("=", "+", "-", "@")


def read_xlsx(path: str) -> List[Block]:
    wb = load_workbook(path, data_only=True)
    wb_formulas = load_workbook(path, data_only=False)
    blocks: List[Block] = []
    for ws, ws_formulas in zip(wb.worksheets, wb_formulas.worksheets):
        rows = []
        for row, row_formulas in zip(ws.iter_rows(), ws_formulas.iter_rows()):
            str_row = []
            for cell, cell_formula in zip(row, row_formulas):
                value = cell.value
                if value is None and isinstance(cell_formula.value, str) and cell_formula.value.startswith("="):
                    # data_only=True gave us None because the workbook was never opened in a
                    # real spreadsheet app (so there's no cached formula result). Fall back to
                    # showing the formula text itself rather than silently dropping the cell.
                    value = cell_formula.value
                str_row.append("" if value is None else str(value))
            if any(cell != "" for cell in str_row):
                rows.append(str_row)
        if rows:
            blocks.append(("table", rows))
    return blocks


def _set_cell(ws, row_idx: int, col_idx: int, value) -> None:
    cell = ws.cell(row=row_idx, column=col_idx, value=value)
    if isinstance(value, str) and value[:1] in _FORMULA_PREFIXES:
        # Force literal-string interpretation so openpyxl (and Excel) doesn't treat
        # e.g. "=SUM(...)" or "-5-3" as a formula to evaluate — it's just text data.
        cell.data_type = "s"


def write_xlsx(blocks: List[Block], path: str) -> None:
    wb = Workbook()
    ws = wb.active
    row_idx = 1
    for kind, content in blocks:
        if kind == "text":
            _set_cell(ws, row_idx, 1, content)
            row_idx += 1
        else:
            for row in content:
                for col_idx, val in enumerate(row, start=1):
                    _set_cell(ws, row_idx, col_idx, val)
                row_idx += 1
    wb.save(path)
