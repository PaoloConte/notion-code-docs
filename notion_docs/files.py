import os
import hashlib
from typing import Iterator, List

from .models import BlockComment
from .comments import extract_block_comments_from_text, parse_breadcrumb_and_strip


SUPPORTED_EXTENSIONS = {".java", ".kt", ".kts"}


def iter_source_files(root: str) -> Iterator[str]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for filename in sorted(filenames):
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

    # Helper to collect NOTION breadcrumbs and text hashes from a single file (no subtree)
    def _collect_from_file(p: str) -> List[tuple]:
        try:
            with open(p, "r", encoding="utf-8") as ff:
                t = ff.read()
        except UnicodeDecodeError:
            with open(p, "r", encoding="latin-1", errors="ignore") as ff:
                t = ff.read()
        _, e = os.path.splitext(p)
        l = ext_to_lang(e)
        entries = []
        for b in extract_block_comments_from_text(t, l):
            parsed = parse_breadcrumb_and_strip(b)
            if parsed is None:
                continue
            bc, rem = parsed
            # Return raw remaining text; aggregation and hashing will be done globally per crumb
            entries.append((tuple(bc), rem))
        return entries

    # First pass: collect NOTION comments in the requested file with text and text_hash only
    results: List[BlockComment] = []
    for body in extract_block_comments_from_text(text, lang):
        parsed = parse_breadcrumb_and_strip(body)
        if parsed is None:
            continue
        breadcrumb, remaining = parsed
        text_hash = hashlib.sha256(remaining.encode("utf-8")).hexdigest()
        results.append(
            BlockComment(
                file_path=path,
                text=remaining,
                breadcrumb=breadcrumb,
                text_hash=text_hash,
                subtree_hash="",
            )
        )

    # Build a global map of crumb -> concatenated text across all files under the same directory as `path`
    base_dir = os.path.dirname(path)
    global_texts: dict[tuple, List[str]] = {}
    for p in iter_source_files(base_dir):
        for crumb, rem in _collect_from_file(p):
            global_texts.setdefault(crumb, []).append(rem)

    # Compute combined text_hash per unique crumb
    combined_hash_by_crumb: dict[tuple, str] = {}
    for crumb, texts in global_texts.items():
        combined_text = "\n".join(texts)
        combined_hash_by_crumb[crumb] = hashlib.sha256(combined_text.encode("utf-8")).hexdigest()

    # Second pass: compute subtree hashes by aggregating combined descendant text hashes across all files
    for i, c in enumerate(results):
        crumb = tuple(c.breadcrumb)
        descendant_hashes: List[tuple] = []
        for other_crumb, h in combined_hash_by_crumb.items():
            if len(crumb) < len(other_crumb) and list(crumb) == list(other_crumb[: len(crumb)]):
                descendant_hashes.append((other_crumb, h))
        descendant_hashes.sort(key=lambda x: x[0])
        combined = "\n".join(h for _path, h in descendant_hashes)
        results[i].subtree_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()

    return results


