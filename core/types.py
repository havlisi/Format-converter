from typing import List, Tuple, Union

Block = Tuple[str, Union[str, List[List[str]]]]


def text_block(content: str) -> Block:
    return ("text", content)


def table_block(rows: List[List[str]]) -> Block:
    return ("table", rows)
