import logging
import re
from typing import List

logger = logging.getLogger(__name__)


def markdown_to_blocks(md: str) -> List[dict]:
    """Very simple Markdown to Notion blocks converter using official API shapes.
    Supports:
    - #, ##, ### headings
    - Bulleted list items (- or *)
    - Code fences ```lang ... ```
    - Paragraphs
    - Inline: **bold**, *italic* (or __ / _), `code`
    This intentionally keeps to structures that are JSON-serializable.
    """

    def make_annotations(*, bold: bool = False, italic: bool = False, code: bool = False) -> dict:
        return {
            "bold": bool(bold),
            "italic": bool(italic),
            "strikethrough": False,
            "underline": False,
            "code": bool(code),
            "color": "default",
        }

    def rich(text: str) -> List[dict]:
        """Convert inline markdown in a text line to Notion rich_text segments.
        Supports **bold**, *italic* / _italic_, and `code` spans.
        Backtick-delimited code segments are not further parsed for bold/italic.
        """
        if not text:
            return []
        segments: List[dict] = []
        # Split by inline code spans, keeping delimiters
        parts = re.split(r'(`[^`]*`)', text)
        for part in parts:
            if not part:
                continue
            if len(part) >= 2 and part.startswith("`") and part.endswith("`"):
                code_text = part[1:-1]
                if code_text:
                    segments.append({
                        "type": "text",
                        "text": {"content": code_text},
                        "annotations": make_annotations(code=True),
                    })
                continue
            # Parse bold/italic in non-code text using a simple state machine
            i = 0
            buf: List[str] = []
            bold = False
            italic = False
            def flush_buf():
                nonlocal buf, bold, italic
                if buf:
                    segments.append({
                        "type": "text",
                        "text": {"content": "".join(buf)},
                        "annotations": make_annotations(bold=bold, italic=italic),
                    })
                    buf = []
            while i < len(part):
                ch = part[i]
                if ch in "*_":
                    # count up to 2 repeated markers
                    count = 1
                    if i + 1 < len(part) and part[i + 1] == ch:
                        count = 2
                    # Toggle styles and do not emit marker characters
                    flush_buf()
                    if count == 2:
                        bold = not bold
                        i += 2
                        continue
                    else:
                        italic = not italic
                        i += 1
                        continue
                else:
                    buf.append(ch)
                    i += 1
            flush_buf()
        return segments or [{"type": "text", "text": {"content": text}}]

    lines = md.splitlines()
    blocks: List[dict] = []
    paragraph_buf: List[str] = []
    in_code = False
    code_lang = None
    code_lines: List[str] = []

    def flush_paragraph():
        nonlocal paragraph_buf
        if paragraph_buf:
            text = " ".join(s.strip() for s in paragraph_buf if s.strip())
            if text:
                blocks.append({"type": "paragraph", "paragraph": {"rich_text": rich(text)}})
            paragraph_buf = []

    def flush_code():
        nonlocal code_lines, code_lang, in_code
        if code_lines:
            blocks.append({
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(code_lines)}}],
                    "language": code_lang or "plain text",
                },
            })
            code_lines = []
            code_lang = None
        in_code = False

    for raw in lines:
        line = raw.rstrip("\n")
        if in_code:
            if line.strip().startswith("```"):
                flush_code()
                continue
            code_lines.append(raw)
            continue

        if line.strip().startswith("```"):
            flush_paragraph()
            # format: ```lang
            code_lang = line.strip()[3:].strip() or None
            in_code = True
            continue

        if not line.strip():
            flush_paragraph()
            continue

        if line.startswith("### "):
            flush_paragraph()
            blocks.append({"type": "heading_3", "heading_3": {"rich_text": rich(line[4:])}})
            continue
        if line.startswith("## "):
            flush_paragraph()
            blocks.append({"type": "heading_2", "heading_2": {"rich_text": rich(line[3:])}})
            continue
        if line.startswith("# "):
            flush_paragraph()
            blocks.append({"type": "heading_1", "heading_1": {"rich_text": rich(line[2:])}})
            continue

        if line.lstrip().startswith("- ") or line.lstrip().startswith("* "):
            flush_paragraph()
            content = line.lstrip()[2:]
            blocks.append({
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": rich(content)},
            })
            continue

        # default: paragraph buffer
        paragraph_buf.append(line)

    if in_code:
        flush_code()
    else:
        flush_paragraph()

    logger.debug("Converted markdown to %d Notion blocks", len(blocks))
    return blocks
