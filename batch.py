import os
from typing import Callable, List, Tuple
from core.dispatch import convert, output_path_for, SUPPORTED_EXTS


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


def find_collisions(file_paths: List[str], target_ext: str) -> List[Tuple[str, str, str]]:
    """Return (first_path, second_path, shared_output_path) for any two input paths
    that would derive the same output path when converted to target_ext.

    Files already in target_ext are excluded since run_batch skips them (no write occurs).
    """
    collisions: List[Tuple[str, str, str]] = []
    seen = {}  # output_path -> first source path that claimed it
    for path in file_paths:
        source_ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if source_ext == target_ext:
            continue
        out_path = output_path_for(path, target_ext)
        if out_path in seen:
            collisions.append((seen[out_path], path, out_path))
        else:
            seen[out_path] = path
    return collisions


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
