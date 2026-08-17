import os
import pytest
from core.dispatch import convert, SUPPORTED_EXTS
from core.csv_io import write_csv


def test_supported_exts():
    assert set(SUPPORTED_EXTS) == {"pdf", "xlsx", "docx", "csv"}


def test_convert_rejects_unsupported_target(tmp_path):
    p = tmp_path / "in.csv"
    write_csv([("table", [["a"]])], str(p))

    with pytest.raises(ValueError, match="unsupported target"):
        convert(str(p), "txt")


def test_convert_rejects_unsupported_source(tmp_path):
    p = tmp_path / "in.txt"
    p.write_text("hi")

    with pytest.raises(ValueError, match="unsupported source"):
        convert(str(p), "csv")


@pytest.mark.parametrize("target_ext", ["xlsx", "docx", "pdf"])
def test_convert_csv_to_every_other_format(tmp_path, target_ext):
    src = tmp_path / "in.csv"
    write_csv([("table", [["Name", "Age"], ["Bob", "30"]])], str(src))

    out_path = convert(str(src), target_ext)

    assert os.path.exists(out_path)
    assert out_path.endswith(f".{target_ext}")


@pytest.mark.parametrize("target_ext", ["pdf", "docx", "csv"])
def test_convert_xlsx_to_every_other_format(tmp_path, target_ext):
    from core.xlsx_io import write_xlsx
    src = tmp_path / "in.xlsx"
    write_xlsx([("table", [["Name", "Age"], ["Bob", "30"]])], str(src))

    out_path = convert(str(src), target_ext)

    assert os.path.exists(out_path)


@pytest.mark.parametrize("target_ext", ["pdf", "xlsx", "csv"])
def test_convert_docx_to_every_other_format(tmp_path, target_ext):
    from core.docx_io import write_docx
    src = tmp_path / "in.docx"
    write_docx([("table", [["Name", "Age"], ["Bob", "30"]])], str(src))

    out_path = convert(str(src), target_ext)

    assert os.path.exists(out_path)


@pytest.mark.parametrize("target_ext", ["xlsx", "docx", "csv"])
def test_convert_pdf_to_every_other_format(tmp_path, target_ext):
    from core.pdf_io import write_pdf
    src = tmp_path / "in.pdf"
    write_pdf([("table", [["Name", "Age"], ["Bob", "30"]])], str(src))

    out_path = convert(str(src), target_ext)

    assert os.path.exists(out_path)
