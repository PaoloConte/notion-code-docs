import re
from typing import List, Tuple

from pygments import lex
from pygments.lexers import JavaLexer, KotlinLexer
from pygments.token import Token


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


def extract_block_comments_from_text(text: str, lang: str) -> List[Tuple[int, int, str]]:
    lexer = JavaLexer() if lang == "java" else KotlinLexer()
    comments: List[Tuple[int, int, str]] = []
    line = 1
    for tok_type, tok_val in lex(text, lexer):
        if tok_type in (Token.Comment.Multiline,):
            start_line = line
            end_line = line + tok_val.count("\n")
            body = _normalize_block_comment_text(tok_val)
            comments.append((start_line, end_line, body))
        line += tok_val.count("\n")
    return comments


