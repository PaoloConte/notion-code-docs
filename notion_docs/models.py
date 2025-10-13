from dataclasses import dataclass


@dataclass
class BlockComment:
    file_path: str
    start_line: int
    end_line: int
    text: str


