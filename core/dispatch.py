from core import pdf_io, xlsx_io, docx_io, csv_io

SUPPORTED_EXTS = ("pdf", "xlsx", "docx", "csv")

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


def convert(source_path: str, target_ext: str) -> str:
    source_ext = source_path.rsplit(".", 1)[-1].lower()
    if source_ext not in SUPPORTED_EXTS:
        raise ValueError(f"unsupported source format: .{source_ext}")
    if target_ext not in SUPPORTED_EXTS:
        raise ValueError(f"unsupported target format: .{target_ext}")

    blocks = _READERS[source_ext](source_path)
    target_path = source_path.rsplit(".", 1)[0] + "." + target_ext
    _WRITERS[target_ext](blocks, target_path)
    return target_path
