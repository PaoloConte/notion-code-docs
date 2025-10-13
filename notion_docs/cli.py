import json
from dataclasses import asdict
from typing import Iterable, List

from .files import iter_source_files, extract_block_comments_from_file, SUPPORTED_EXTENSIONS
from .models import BlockComment


def run(root: str, exts: Iterable[str]) -> List[BlockComment]:
    results: List[BlockComment] = []
    for path in iter_source_files(root):
        if any(path.endswith(e if e.startswith('.') else f'.{e}') for e in exts):
            results.extend(extract_block_comments_from_file(path))
    return results


def print_results(results: Iterable[BlockComment], as_json: bool) -> None:
    if as_json:
        print(json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2))
        return
    for r in results:
        print(f"{r.file_path}")
        print(f"Breadcrumb: {' > '.join(r.breadcrumb)}")
        print("/*")
        print(r.text)
        print("*/\n")


