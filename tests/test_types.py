# converter/tests/test_types.py
from core.types import text_block, table_block


def test_text_block_shape():
    b = text_block("hello")
    assert b == ("text", "hello")


def test_table_block_shape():
    b = table_block([["a", "b"], ["1", "2"]])
    assert b == ("table", [["a", "b"], ["1", "2"]])
