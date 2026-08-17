import os
from typing import Callable, List
from core.dispatch import convert, SUPPORTED_EXTS


def scan_folder(folder_path: str) -> List[str]:
    found = []
    for name in os.listdir(folder_path):
        full = os.path.join(folder_path, name)
        if not os.path.isfile(full):
            continue
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext in SUPPORTED_EXTS:
            found.append(full)
    return sorted(found)


def run_batch(file_paths: List[str], target_ext: str, on_row_update: Callable[[str, str], None]) -> None:
    for path in file_paths:
        source_ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if source_ext == target_ext:
            on_row_update(path, f"skipped (already {target_ext})")
            continue
        try:
            out_path = convert(path, target_ext)
            on_row_update(path, f"done -> {out_path}")
        except Exception as e:
            on_row_update(path, f"error: {e}")
