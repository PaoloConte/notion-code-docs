import os
from typing import Iterator, List

from .models import BlockComment
from .comments import extract_block_comments_from_text, parse_breadcrumb_and_strip


SUPPORTED_EXTENSIONS = {".java", ".kt", ".kts"}


def iter_source_files(root: str) -> Iterator[str]:
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            _, ext = os.path.splitext(filename)
            if ext in SUPPORTED_EXTENSIONS:
                yield os.path.join(dirpath, filename)


def ext_to_lang(ext: str) -> str:
    if ext == ".java":
        return "java"
    return "kotlin"


def extract_block_comments_from_file(path: str) -> List[BlockComment]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="latin-1", errors="ignore") as f:
            text = f.read()

    _, ext = os.path.splitext(path)
    lang = ext_to_lang(ext)

    results: List[BlockComment] = []
    for comment in extract_block_comments_from_text(text, lang):
        parsed = parse_breadcrumb_and_strip(comment.text)
        if parsed is None:
            continue
        breadcrumb, remaining = parsed
        results.append(
            BlockComment(
                file_path=path,
                text=remaining,
                breadcrumb=breadcrumb,
            )
        )
    return results


