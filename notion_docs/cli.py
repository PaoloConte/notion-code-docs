import argparse
import json
from dataclasses import asdict
from typing import Iterable, List, Optional, Sequence

from .files import iter_source_files, extract_block_comments_from_file, SUPPORTED_EXTENSIONS
from .models import BlockComment


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract block comments from Java/Kotlin source files.")
    parser.add_argument("root", help="Root directory to scan")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--ext", nargs="*", default=sorted(SUPPORTED_EXTENSIONS), help="File extensions to include (e.g., kt kts java)")
    return parser.parse_args(argv)


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
        print(f"{r.file_path}:{r.start_line}-{r.end_line}")
        print("/*")
        print(r.text)
        print("*/\n")


