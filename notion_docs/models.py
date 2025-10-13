from dataclasses import dataclass
from typing import List


@dataclass
class BlockComment:
    file_path: str
    text: str  # comment body with breadcrumb removed
    breadcrumb: List[str]


