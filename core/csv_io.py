import csv
from core.types import Block
from typing import List


def read_csv(path: str) -> List[Block]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        return []
    return [("table", rows)]


def write_csv(blocks: List[Block], path: str) -> None:
    out_rows = []
    for kind, content in blocks:
        if kind == "table":
            out_rows.extend(content)
        else:
            out_rows.append([content])
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(out_rows)
