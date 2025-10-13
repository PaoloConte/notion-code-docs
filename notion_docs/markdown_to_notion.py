import logging
from typing import List

from markdown_it import MarkdownIt
from markdown_it.token import Token

logger = logging.getLogger(__name__)


def markdown_to_blocks(md: str) -> List[dict]:
    """Convert Markdown to Notion blocks using a structured Markdown parser (markdown-it-py).
    Supported blocks: headings (h1–h3), paragraphs, bulleted lists, fenced code.
    Supported inline: bold, italic, inline code.
    """
    md = md or ""
    md_parser = MarkdownIt("commonmark")
    tokens: List[Token] = md_parser.parse(md)

    def make_annotations(*, bold: bool = False, italic: bool = False, code: bool = False) -> dict:
        return {
            "bold": bool(bold),
            "italic": bool(italic),
            "strikethrough": False,
            "underline": False,
            "code": bool(code),
            "color": "default",
        }

    def rich_from_inline(inline: Token) -> List[dict]:
        bold = False
        italic = False
        segments: List[dict] = []
        buf: List[str] = []

        def flush_buf():
            nonlocal buf, bold, italic
            if buf:
                segments.append({
                    "type": "text",
                    "text": {"content": "".join(buf)},
                    "annotations": make_annotations(bold=bold, italic=italic),
                })
                buf.clear()

        for t in inline.children or []:
            if t.type == "text":
                buf.append(t.content)
            elif t.type == "code_inline":
                flush_buf()
                segments.append({
                    "type": "text",
                    "text": {"content": t.content},
                    "annotations": make_annotations(code=True),
                })
            elif t.type == "strong_open":
                flush_buf()
                bold = True
            elif t.type == "strong_close":
                flush_buf()
                bold = False
            elif t.type == "em_open":
                flush_buf()
                italic = True
            elif t.type == "em_close":
                flush_buf()
                italic = False
            elif t.type in ("softbreak", "hardbreak"):
                buf.append(" ")
            else:
                # Skip unsupported inline tokens safely
                pass
        flush_buf()
        return segments

    blocks: List[dict] = []
    i = 0

    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1]) if tok.tag.startswith("h") else 1
            inline = tokens[i + 1] if i + 1 < len(tokens) and tokens[i + 1].type == "inline" else None
            content = rich_from_inline(inline) if inline else []
            level = max(1, min(level, 3))
            key = f"heading_{level}"
            blocks.append({"type": key, key: {"rich_text": content}})
            # skip inline and heading_close
            i += 3
            continue

        if tok.type == "paragraph_open":
            inline = tokens[i + 1] if i + 1 < len(tokens) and tokens[i + 1].type == "inline" else None
            content = rich_from_inline(inline) if inline else []
            blocks.append({"type": "paragraph", "paragraph": {"rich_text": content}})
            i += 3
            continue

        if tok.type == "bullet_list_open":
            # iterate list items until bullet_list_close
            i += 1
            while i < len(tokens) and tokens[i].type != "bullet_list_close":
                if tokens[i].type == "list_item_open":
                    # structure: list_item_open, paragraph_open, inline, paragraph_close, list_item_close
                    # or list_item_open, inline? handle flexibly
                    # find the first inline inside the list item
                    j = i + 1
                    inline = None
                    while j < len(tokens) and tokens[j].type != "list_item_close":
                        if tokens[j].type == "inline":
                            inline = tokens[j]
                            break
                        j += 1
                    content = rich_from_inline(inline) if inline else []
                    blocks.append({
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {"rich_text": content},
                    })
                    # advance to list_item_close
                    while i < len(tokens) and tokens[i].type != "list_item_close":
                        i += 1
                    # consume list_item_close
                    i += 1
                else:
                    i += 1
            # consume bullet_list_close
            i += 1
            continue

        if tok.type == "fence":
            language = (tok.info or "").strip() or "plain text"
            blocks.append({
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": tok.content.rstrip('\n')}}],
                    "language": language,
                },
            })
            i += 1
            continue

        # Skip other token types (the close tokens will be consumed by their handlers)
        i += 1

    logger.debug("Converted markdown to %d Notion blocks via markdown-it-py", len(blocks))
    return blocks
