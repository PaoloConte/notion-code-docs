import os
import hashlib
from typing import Iterator, List, Tuple, Dict, Set, Optional
import re

from .models import BlockComment
from .comments import extract_block_comments_from_text, parse_breadcrumb_and_strip
from .mnemonic import compute_mnemonic


SUPPORTED_EXTENSIONS = {".java", ".kt", ".kts", ".php", ".md"}


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
    if ext == ".php":
        return "php"
    if ext == ".md":
        return "markdown"
    return "kotlin"


def _strip_sort_index(breadcrumb: List[str]) -> Tuple[List[str], Optional[int]]:
    """If the last breadcrumb segment ends with #<number>, strip it and return the number.

    Example: ["A", "B#3"] -> (["A", "B"], 3)
    Only matches if '#' is immediately followed by digits at the end of the last segment.
    """
    if not breadcrumb:
        return breadcrumb, None
    last = breadcrumb[-1]
    m = re.match(r"^(.*?)(?:#(\d+))$", last)
    if m:
        base, num = m.group(1), m.group(2)
        cleaned = breadcrumb[:-1] + [base]
        try:
            return cleaned, int(num)
        except ValueError:
            return cleaned, None
    return breadcrumb, None


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
            # Normalize breadcrumb by stripping any trailing #<num> from the last segment
            cleaned_bc, _ = _strip_sort_index(list(bc))
            # Return raw remaining text; aggregation and hashing will be done globally per crumb
            entries.append((tuple(cleaned_bc), rem))
        return entries

    # First pass: collect NOTION comments in the requested file with text and text_hash only
    results: List[BlockComment] = []
    for body in extract_block_comments_from_text(text, lang):
        parsed = parse_breadcrumb_and_strip(body)
        if parsed is None:
            continue
        breadcrumb, remaining = parsed
        # Extract optional sort_index and clean breadcrumb
        cleaned_breadcrumb, sort_index = _strip_sort_index(list(breadcrumb))
        text_hash = hashlib.sha256(remaining.encode("utf-8")).hexdigest()
        results.append(
            BlockComment(
                file_path=path,
                text=remaining,
                breadcrumb=cleaned_breadcrumb,
                sort_index=sort_index,
                text_hash=text_hash,
                subtree_hash="",
            )
        )

    # Build a global map of crumb -> concatenated text across all files under the same directory as `path`
    base_dir = os.path.dirname(path)

    # First collect all raw crumbs/texts from the tree to build a mnemonic map
    raw_global_entries: List[Tuple[Tuple[str, ...], str]] = []
    for p in iter_source_files(base_dir):
        for crumb, rem in _collect_from_file(p):
            raw_global_entries.append((crumb, rem))

    # Build mnemonic -> set of observed titles (segment strings) across all crumbs
    mnemo_to_titles: Dict[str, Set[str]] = {}
    observed_titles: Set[str] = set()
    for crumb, _ in raw_global_entries:
        for seg in crumb:
            observed_titles.add(seg)

    def is_potential_mnemonic(s: str) -> bool:
        # Consider 3-char uppercase strings that equal their own mnemonic as mnemonic tokens
        return len(s) == 3 and compute_mnemonic(s) == s.upper()

    # Populate mnemonic map using only non-mnemonic-looking titles, so that
    # mnemonic placeholders in breadcrumbs don't pollute uniqueness checks
    for title in observed_titles:
        if is_potential_mnemonic(title):
            continue
        m = compute_mnemonic(title)
        mnemo_to_titles.setdefault(m, set()).add(title)

    def resolve_segment(seg: str) -> str:
        # If seg is exactly a known non-mnemonic-looking title, keep as is
        if seg in observed_titles and not is_potential_mnemonic(seg):
            return seg
        # If looks like a 3-char mnemonic, try to resolve to a unique title
        if len(seg) == 3:
            m = seg.upper()
            titles = mnemo_to_titles.get(m)
            if titles and len(titles) == 1:
                return next(iter(titles))
        return seg

    def resolve_crumb(crumb: Tuple[str, ...]) -> Tuple[str, ...]:
        return tuple(resolve_segment(s) for s in crumb)

    # Group texts by resolved crumbs
    global_texts: Dict[Tuple[str, ...], List[str]] = {}
    for crumb, rem in raw_global_entries:
        rcrumb = resolve_crumb(crumb)
        global_texts.setdefault(rcrumb, []).append(rem)

    # Compute combined text_hash per unique resolved crumb
    combined_hash_by_crumb: Dict[Tuple[str, ...], str] = {}
    for crumb, texts in global_texts.items():
        combined_text = "\n".join(texts)
        combined_hash_by_crumb[crumb] = hashlib.sha256(combined_text.encode("utf-8")).hexdigest()

    # Resolve breadcrumbs for current file results as well
    for r in results:
        r.breadcrumb = list(resolve_crumb(tuple(r.breadcrumb)))

    # Second pass: compute subtree hashes by aggregating combined descendant text hashes across all files
    for i, c in enumerate(results):
        crumb = tuple(c.breadcrumb)
        descendant_hashes: List[Tuple[Tuple[str, ...], str]] = []
        for other_crumb, h in combined_hash_by_crumb.items():
            if len(crumb) < len(other_crumb) and list(crumb) == list(other_crumb[: len(crumb)]):
                descendant_hashes.append((other_crumb, h))
        descendant_hashes.sort(key=lambda x: x[0])
        combined = "\n".join(h for _path, h in descendant_hashes)
        results[i].subtree_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()

    return results


