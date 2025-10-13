import re
from typing import List, Optional, Tuple

from pygments import lex
from pygments.lexers import JavaLexer, KotlinLexer
from pygments.token import Token

from .models import BlockComment


def _normalize_block_comment_text(raw: str) -> str:
    without_delims = re.sub(r'^\s*/\*+\s?', '', raw)
    without_delims = re.sub(r'\s*\*+/\s*$', '', without_delims)

    lines = [re.sub(r'^\s*\*+\s?', '', line) for line in without_delims.splitlines()]

    while lines and lines[0].strip() == '':
        lines.pop(0)
    while lines and lines[-1].strip() == '':
        lines.pop()

    if not lines:
        return ""

    leading_ws = []
    for line in lines:
        if line.strip() == '':
            continue
        m = re.match(r"^[\t ]*", line)
        leading_ws.append(m.group(0) if m else "")

    if leading_ws:
        common_prefix = leading_ws[0]
        for ws in leading_ws[1:]:
            while not ws.startswith(common_prefix) and common_prefix:
                common_prefix = common_prefix[:-1]
        if common_prefix:
            lines = [line[len(common_prefix):] if line.startswith(common_prefix) else line for line in lines]

    return "\n".join(lines)


def extract_block_comments_from_text(text: str, lang: str) -> List[BlockComment]:
    lexer = JavaLexer() if lang == "java" else KotlinLexer()
    comments: List[BlockComment] = []
    line = 1
    for tok_type, tok_val in lex(text, lexer):
        if tok_type in (Token.Comment.Multiline,):
            start_line = line
            end_line = line + tok_val.count("\n")
            body = _normalize_block_comment_text(tok_val)
            comments.append(
                BlockComment(
                    file_path="",
                    text=body,
                    breadcrumb=[],
                )
            )
        line += tok_val.count("\n")
    return comments


def parse_breadcrumb_and_strip(body: str) -> Optional[Tuple[List[str], str]]:
    """Parse a NOTION.* breadcrumb at the start of body and strip it.

    Returns a tuple (breadcrumb, remaining_text) if present, otherwise None.
    Breadcrumb segments are split on '.' after the NOTION. prefix and may
    include spaces or symbols as part of each segment. The only delimiter is '.'.
    """
    if not body.startswith("NOTION."):
        return None
    # Determine token boundary:
    # - If a newline exists, the token runs until the newline (spaces allowed inside segments)
    # - Otherwise (single-line), the token runs until the first space/tab (if any)
    idx_nl = body.find("\n")
    if idx_nl != -1:
        token_end = idx_nl
    else:
        # Single-line: decide if the first space separates breadcrumb from body.
        first_space = body.find(" ")
        if first_space == -1:
            token_end = len(body)
        else:
            tail = body[first_space+1:].strip()
            if (" " in tail) or ("\t" in tail):
                token_end = first_space
            else:
                token_end = len(body)

    token = body[:token_end]
    rest = body[token_end:]
    # Strip only leading whitespace/newlines from the remaining text
    rest = rest.lstrip(" \t\n")

    # token is like NOTION.A.B.C — extract segments after NOTION.
    segments_part = token[len("NOTION."):]
    segments = segments_part.split(".") if segments_part else []
    # Special case: if no '.' was present (single segment), allow splitting by whitespace
    if len(segments) == 1:
        only = segments[0].strip()
        if only:
            # Split on any run of whitespace
            parts = [p for p in re.split(r"\s+", only) if p]
            segments = parts
    # If there is no remaining text and the token contained spaces, emit the last
    # whitespace-delimited word as remaining text to preserve trailing label like "C"
    if not rest and (" " in segments_part or "\t" in segments_part):
        words = [w for w in re.split(r"\s+", segments_part) if w]
        if words:
            rest = words[-1]
    return (segments, rest)


