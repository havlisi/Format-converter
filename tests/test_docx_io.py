from core.docx_io import read_docx, write_docx


def test_write_then_read_text_block(tmp_path):
    p = tmp_path / "out.docx"
    blocks = [("text", "Hello world")]

    write_docx(blocks, str(p))
    result = read_docx(str(p))

    assert result == [("text", "Hello world")]


def test_write_then_read_table_block(tmp_path):
    p = tmp_path / "out2.docx"
    blocks = [("table", [["Name", "Age"], ["Bob", "30"]])]

    write_docx(blocks, str(p))
    result = read_docx(str(p))

    assert result == [("table", [["Name", "Age"], ["Bob", "30"]])]


def test_order_preserved_text_then_table(tmp_path):
    p = tmp_path / "out3.docx"
    blocks = [("text", "Intro"), ("table", [["x", "y"]])]

    write_docx(blocks, str(p))
    result = read_docx(str(p))

    assert result == [("text", "Intro"), ("table", [["x", "y"]])]
