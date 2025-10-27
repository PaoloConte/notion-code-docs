from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class BlockComment:
    file_path: str
    text: str  # comment body with breadcrumb removed
    breadcrumb: List[str]
    # Optional sort index to order comments within the same breadcrumb
    sort_index: Optional[int] = None
    # Hash of the comment text (normalized and with breadcrumb removed)
    text_hash: str = ""
    # Hash including the breadcrumb hierarchy (represents the subtree identity)
    subtree_hash: str = ""
    # Options extracted from tag, e.g., NOTION[option1,option2].page
    options: Dict[str, bool] = field(default_factory=dict)


