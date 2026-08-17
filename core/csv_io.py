import csv
from core.types import Block
from typing import List


def read_csv(path: str) -> List[Block]:
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    except UnicodeDecodeError:
        # Common case: a CSV exported from Excel on Windows using the legacy
        # Western-European codepage instead of UTF-8. Fall back before giving up;
        # any further failure propagates to the caller (batch.py reports it).
        with open(path, newline="", encoding="cp1252") as f:
            rows = list(csv.reader(f))
    if not rows:
        return []
    return [("table", rows)]


def write_csv(blocks: List[Block], path: str) -> None:
    out_rows = []
    prev_kind = None
    for kind, content in blocks:
        # Separate consecutive tables (e.g. one per XLSX sheet) with a blank
        # row so they don't merge into one ragged table on read-back.
        if kind == "table" and prev_kind == "table":
            out_rows.append([])
        if kind == "table":
            out_rows.extend(content)
        else:
            out_rows.append([content])
        prev_kind = kind
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(out_rows)
