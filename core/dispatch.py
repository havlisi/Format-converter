import os
from core import pdf_io, xlsx_io, docx_io, csv_io

SUPPORTED_EXTS = ("pdf", "xlsx", "docx", "csv")


def ext_of(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[1].lstrip(".").lower()

_READERS = {
    "pdf": pdf_io.read_pdf,
    "xlsx": xlsx_io.read_xlsx,
    "docx": docx_io.read_docx,
    "csv": csv_io.read_csv,
}

_WRITERS = {
    "pdf": pdf_io.write_pdf,
    "xlsx": xlsx_io.write_xlsx,
    "docx": docx_io.write_docx,
    "csv": csv_io.write_csv,
}

# Pairs where a faithful conversion cannot go through the (text, table) Block
# model — handed straight to a specialist that reads the source and writes the
# target itself. Checked before the generic reader/writer pipeline.
_DIRECT_ROUTES = {
    ("pdf", "docx"): docx_io.pdf_to_docx,   # (source_path, target_path) -> None
}


def output_path_for(source_path: str, target_ext: str) -> str:
    return source_path.rsplit(".", 1)[0] + "." + target_ext


def convert(source_path: str, target_ext: str) -> str:
    source_ext = ext_of(source_path)
    target_ext = target_ext.lower()
    if source_ext not in SUPPORTED_EXTS:
        raise ValueError(f"unsupported source format: .{source_ext or '(none)'}")
    if target_ext not in SUPPORTED_EXTS:
        raise ValueError(f"unsupported target format: .{target_ext or '(none)'}")

    route = _DIRECT_ROUTES.get((source_ext, target_ext))
    if route:
        target_path = output_path_for(source_path, target_ext)
        route(source_path, target_path)
        return target_path

    blocks = _READERS[source_ext](source_path)
    if not blocks:
        raise ValueError("source file has no content to convert")
    target_path = output_path_for(source_path, target_ext)
    _WRITERS[target_ext](blocks, target_path)
    return target_path
