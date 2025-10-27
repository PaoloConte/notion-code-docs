import re
from typing import Dict, List, Optional, Tuple

from pygments import lex
from pygments.lexers import JavaLexer, KotlinLexer, PhpLexer
from pygments.token import Token



def _normalize_block_comment_text(raw: str) -> str:
    # Replace opening and closing block comment delimiters with same-length spaces,
    # preserving surrounding spaces. Do not trim inner content yet.
    def replace_opening(m: re.Match) -> str:
        token = m.group(0)
        # Replace only the '/**' or '/*' part with spaces; keep any following space intact
        stars = re.match(r"/\*+", token)
        if not stars:
            return token
        return " " * len(stars.group(0)) + token[len(stars.group(0)) :]

    def replace_closing(m: re.Match) -> str:
        token = m.group(0)
        # Replace only the '*/' part (with leading *s) with spaces; keep preceding spaces intact
        stars = re.search(r"\*+/", token)
        if not stars:
            return token
        start, end = stars.span()
        return token[:start] + (" " * (end - start)) + token[end:]

    # Apply only at the very start and very end of the comment token
    s = re.sub(r"^/\*+ ?", replace_opening, raw)
    s = re.sub(r" ?\*+/\s*$", replace_closing, s)

    lines = s.splitlines()

    # Remove leading/trailing completely empty lines
    while lines and lines[0].strip() == "":
        lines.pop(0)
    while lines and lines[-1].strip() == "":
        lines.pop()

    if not lines:
        return ""

    def trim_common_indent(ls: List[str]) -> List[str]:
        # Compute common leading whitespace among non-empty lines and trim it
        non_empty = [l for l in ls if l.strip() != ""]
        if not non_empty:
            return ls
        prefixes = []
        for l in non_empty:
            m = re.match(r"^[\t ]*", l)
            prefixes.append(m.group(0) if m else "")
        common = prefixes[0]
        for ws in prefixes[1:]:
            while not ws.startswith(common) and common:
                common = common[:-1]
        if not common:
            return ls
        return [l[len(common):] if l.startswith(common) else l for l in ls]

    # First: trim maximum common indentation
    lines = trim_common_indent(lines)

    # Star-strip if all non-empty lines start with '*', or if all lines EXCEPT the first non-empty start with '*'.
    # This ignores the first line which may contain the opening '/*' content on the same line.
    non_empty_lines = [l for l in lines if l.strip() != ""]

    def is_star_line(l: str) -> bool:
        # Consider lines that start with '*' or with a single leading space/tab before '*'
        return bool(re.match(r"^[ \t]?\*", l))

    def is_breadcrumb_line(l: str) -> bool:
        ls = l.lstrip()
        return ls.startswith("NOTION.") or ls.startswith("NOTION/") or ls.startswith("NOTION[")

    should_star_strip = False
    if non_empty_lines:
        # Case 1: every non-empty line starts with '*'
        if all(is_star_line(l) for l in non_empty_lines):
            should_star_strip = True
        else:
            # Case 2: ignore the first non-empty line when checking (it may start with '/')
            tail = non_empty_lines[1:]
            if tail and all(is_star_line(l) for l in tail):
                should_star_strip = True
            # Preserve breadcrumb-first special case as well
            elif is_breadcrumb_line(non_empty_lines[0]) and all(is_star_line(l) for l in non_empty_lines[1:]):
                should_star_strip = True

    if should_star_strip:
        new_lines: List[str] = []
        for l in lines:
            if l.startswith("*"):
                l = l[1:]
                if l.startswith(" "):
                    l = l[1:]
            elif l.startswith(" *"):
                # Remove a single leading space/tab before '*', then behave like above
                l = l[2:]
                if l.startswith(" "):
                    l = l[1:]
            new_lines.append(l)
        lines = new_lines
        lines = trim_common_indent(lines)

    # Remove leading/trailing completely empty lines again
    while lines and lines[0].strip() == "":
        lines.pop(0)
    while lines and lines[-1].strip() == "":
        lines.pop()

    # Ensure breadcrumb line is not indented: strip leading spaces/tabs if first line is NOTION.*
    if lines and re.match(r"^\s*NOTION[\.\[/]", lines[0]):
        lines[0] = lines[0].lstrip(" \t")
        # If subsequent lines are visually aligned with the breadcrumb due to extra indentation,
        # remove their common leading whitespace equally.
        tail_non_empty = [l for l in lines[1:] if l.strip() != ""]
        if tail_non_empty:
            # Compute common leading whitespace among tail non-empty lines
            def leading_ws(s: str) -> str:
                m = re.match(r"^[\t ]*", s)
                return m.group(0) if m else ""
            common_ws = leading_ws(tail_non_empty[0])
            for t in tail_non_empty[1:]:
                ws = leading_ws(t)
                # Reduce common prefix to the shared part
                while not ws.startswith(common_ws) and common_ws:
                    common_ws = common_ws[:-1]
            if common_ws:
                new_tail: List[str] = []
                for l in lines[1:]:
                    if l.startswith(common_ws):
                        new_tail.append(l[len(common_ws):])
                    else:
                        new_tail.append(l)
                lines = [lines[0]] + new_tail

    lines = [l if l.strip() else "" for l in lines]
    return "\n".join(lines).rstrip()


def extract_block_comments_from_text(text: str, lang: str) -> List[str]:
    if lang == "markdown":
        return [text.strip("\n")]
    elif lang == "java":
        lexer = JavaLexer()
    elif lang == "kotlin":
        lexer = KotlinLexer()
    elif lang == "php":
        lexer = PhpLexer()
    else:
        # Default to Kotlin-style (C-style comments) if unknown
        lexer = KotlinLexer()
    bodies: List[str] = []
    line = 1
    for tok_type, tok_val in lex(text, lexer):
        if tok_type in (Token.Comment.Multiline,):
            body = _normalize_block_comment_text(tok_val)
            bodies.append(body)
        line += tok_val.count("\n")
    return bodies


def parse_breadcrumb_and_strip(body: str) -> Optional[Tuple[List[str], str, Dict[str, bool]]]:
    """Parse a NOTION.* breadcrumb at the start of body and strip it.

    Returns a tuple (breadcrumb, remaining_text, options) if present, otherwise None.
    Breadcrumb segments are split on '.' or '/' after the NOTION prefix and may
    include spaces or symbols as part of each segment. The delimiters are '.' and '/'.
    Options can be specified in brackets: NOTION[option1,option2].page.path
    """
    # Extract options from brackets if present (e.g., NOTION[include_all].page)
    options: Dict[str, bool] = {}
    if body.startswith("NOTION["):
        # Find the closing bracket
        closing_bracket = body.find("]")
        if closing_bracket != -1:
            # Extract options from within brackets
            options_str = body[len("NOTION["):closing_bracket]
            # Parse comma-separated options
            for opt in options_str.split(","):
                opt = opt.strip()
                if opt:
                    options[opt] = True
            # Remove the bracket part from body
            body = "NOTION" + body[closing_bracket + 1:]

    if not (body.startswith("NOTION.") or body.startswith("NOTION/")):
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

    # token is like NOTION.A/B.C — extract segments after NOTION separator ('.' or '/')
    sep = token[len("NOTION"):len("NOTION")+1] if len(token) > len("NOTION") else "."
    if sep not in (".", "/"):
        sep = "."
    segments_part = token[len("NOTION")+1:]
    # Split on both '.' and '/'
    segments = [p for p in re.split(r"[\./]", segments_part) if p] if segments_part else []
    # Special case: Check if this is NOTION.* or NOTION/* with text after
    # If so, only keep "*" as the segment and move the rest to comment text
    if segments_part.strip() == "*" or (segments_part.startswith("* ") or segments_part.startswith("*\t")):
        segments = ["*"]
        # Everything after "* " becomes rest
        idx = segments_part.find("*")
        if idx != -1 and idx + 1 < len(segments_part):
            after_star = segments_part[idx + 1:].lstrip(" \t")
            if after_star:
                rest = after_star if not rest else after_star + "\n" + rest
    else:
        # Special case: if no '.' or '/' was present (single segment), allow splitting by whitespace
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
    return (segments, rest, options)


