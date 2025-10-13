import logging
from typing import List, Optional, Any, Dict

from markdown_it import MarkdownIt
from markdown_it.token import Token

logger = logging.getLogger(__name__)


def markdown_to_blocks(md: str) -> List[dict]:
    """Convert Markdown to Notion blocks using a structured Markdown parser (markdown-it-py).
    Supported blocks: headings (h1–h3), paragraphs, bulleted lists, fenced code, simple tables.
    Supported inline: bold, italic, inline code.
    """
    md = md or ""
    md_parser = MarkdownIt("commonmark").enable('table')
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
        current_link: Optional[str] = None
        segments: List[dict] = []
        buf: List[str] = []

        def flush_buf():
            nonlocal buf, bold, italic, current_link
            if buf:
                text_obj: Dict[str, Any] = {"content": "".join(buf)}
                if current_link:
                    text_obj["link"] = {"url": current_link}
                segments.append({
                    "type": "text",
                    "text": text_obj,
                    "annotations": make_annotations(bold=bold, italic=italic),
                })
                buf.clear()

        for t in inline.children or []:
            if t.type == "text":
                buf.append(t.content)
            elif t.type == "code_inline":
                flush_buf()
                text_obj: Dict[str, Any] = {"content": t.content}
                if current_link:
                    text_obj["link"] = {"url": current_link}
                segments.append({
                    "type": "text",
                    "text": text_obj,
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
            elif t.type == "link_open":
                flush_buf()
                try:
                    href = t.attrGet("href")
                except Exception:
                    href = None
                current_link = href
            elif t.type == "link_close":
                flush_buf()
                current_link = None
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

        if tok.type == "table_open":
            # Parse a simple GFM-style table into a Notion table block
            has_header = False
            rows: List[dict] = []
            table_width = 0
            i += 1
            # optional thead
            if i < len(tokens) and tokens[i].type == "thead_open":
                has_header = True
                i += 1  # into thead
                while i < len(tokens) and tokens[i].type != "thead_close":
                    if tokens[i].type == "tr_open":
                        i += 1
                        cells_rt: List[List[dict]] = []
                        while i < len(tokens) and tokens[i].type != "tr_close":
                            if tokens[i].type in ("th_open", "td_open"):
                                # inline is next significant token before th/td_close
                                inline = None
                                j = i + 1
                                while j < len(tokens) and tokens[j].type not in ("th_close", "td_close"):
                                    if tokens[j].type == "inline":
                                        inline = tokens[j]
                                        break
                                    j += 1
                                cell_rich = rich_from_inline(inline) if inline else []
                                cells_rt.append(cell_rich)
                                # advance to cell close
                                while i < len(tokens) and tokens[i].type not in ("th_close", "td_close"):
                                    i += 1
                                i += 1  # consume close
                            else:
                                i += 1
                        table_width = max(table_width, len(cells_rt))
                        rows.append({
                            "type": "table_row",
                            "table_row": {"cells": cells_rt},
                        })
                        i += 1  # consume tr_close
                    else:
                        i += 1
                i += 1  # consume thead_close
            # tbody (common path)
            if i < len(tokens) and tokens[i].type == "tbody_open":
                i += 1
                while i < len(tokens) and tokens[i].type != "tbody_close":
                    if tokens[i].type == "tr_open":
                        i += 1
                        cells_rt: List[List[dict]] = []
                        while i < len(tokens) and tokens[i].type != "tr_close":
                            if tokens[i].type in ("th_open", "td_open"):
                                inline = None
                                j = i + 1
                                while j < len(tokens) and tokens[j].type not in ("th_close", "td_close"):
                                    if tokens[j].type == "inline":
                                        inline = tokens[j]
                                        break
                                    j += 1
                                cell_rich = rich_from_inline(inline) if inline else []
                                cells_rt.append(cell_rich)
                                while i < len(tokens) and tokens[i].type not in ("th_close", "td_close"):
                                    i += 1
                                i += 1  # consume close
                            else:
                                i += 1
                        table_width = max(table_width, len(cells_rt))
                        rows.append({
                            "type": "table_row",
                            "table_row": {"cells": cells_rt},
                        })
                        i += 1  # consume tr_close
                    else:
                        i += 1
                i += 1  # consume tbody_close
            # consume table_close if present
            if i < len(tokens) and tokens[i].type == "table_close":
                i += 1
            # Normalize each row to table_width by padding empty cells
            for r in rows:
                cells = r["table_row"]["cells"]
                if len(cells) < table_width:
                    # pad with empty rich_text cells
                    cells.extend([[] for _ in range(table_width - len(cells))])
                elif len(cells) > table_width and table_width > 0:
                    del cells[table_width:]
            table_block = {
                "type": "table",
                "table": {
                    "table_width": table_width or 0,
                    "has_column_header": has_header,
                    "has_row_header": False,
                },
                "children": rows,
            }
            blocks.append(table_block)
            continue

        # Skip other token types (the close tokens will be consumed by their handlers)
        i += 1

    logger.debug("Converted markdown to %d Notion blocks via markdown-it-py", len(blocks))
    return blocks
