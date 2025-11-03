import logging
from typing import List, Optional, Any, Dict

from markdown_it import MarkdownIt
from markdown_it.token import Token
from urllib.parse import urlparse
import re

logger = logging.getLogger(__name__)


def markdown_to_blocks(md: str) -> List[dict]:
    """Convert Markdown to Notion blocks using a structured Markdown parser (markdown-it-py).
    Supported blocks: headings (h1–h3), paragraphs, blockquotes, bulleted lists, fenced code, simple tables.
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

    def is_notion_url(url: Optional[str]) -> bool:
        if not url:
            return False
        try:
            u = urlparse(url)
            host = (u.netloc or "").lower()
            # notion main domains and public site domains
            return host.endswith("notion.so") or host.endswith("notion.site")
        except Exception:
            return False

    def extract_page_id(url: Optional[str]) -> Optional[str]:
        """Extract and normalize a Notion page ID from the given URL.
        Returns hyphenated lowercase UUID if found, else None.
        """
        if not url:
            return None
        m = re.search(r"([0-9a-fA-F]{32}|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})", url)
        if not m:
            return None
        token = m.group(1).lower()
        if len(token) == 32:
            # insert dashes 8-4-4-4-12
            return f"{token[0:8]}-{token[8:12]}-{token[12:16]}-{token[16:20]}-{token[20:32]}"
        return token

    def rich_from_inline(inline: Token) -> List[dict]:
        bold = False
        italic = False
        current_link: Optional[str] = None
        segments: List[dict] = []
        buf: List[str] = []

        def flush_buf():
            nonlocal buf, bold, italic, current_link
            if buf:
                content_text = "".join(buf)
                if current_link and is_notion_url(current_link):
                    page_id = extract_page_id(current_link)
                    if page_id:
                        segments.append({
                            "type": "mention",
                            "mention": {
                                "type": "page",
                                "page": {"id": page_id},
                            },
                            "annotations": make_annotations(bold=bold, italic=italic),
                            "plain_text": content_text,
                            "href": current_link,
                        })
                        buf.clear()
                        return
                # default: plain text (possibly linked)
                text_obj: Dict[str, Any] = {"content": content_text}
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
                # If inside a Notion link, emit a mention segment with the code content as plain_text
                if current_link and is_notion_url(current_link):
                    page_id = extract_page_id(current_link)
                    if page_id:
                        segments.append({
                            "type": "mention",
                            "mention": {
                                "type": "page",
                                "page": {"id": page_id},
                            },
                            "annotations": make_annotations(code=True),
                            "plain_text": t.content,
                            "href": current_link,
                        })
                        continue
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
            elif t.type == "softbreak":
                buf.append(" ")
            elif t.type == "hardbreak":
                # Preserve explicit hard line breaks (two trailing spaces or backslash EOL)
                # by inserting a newline into the text buffer. This avoids relying on
                # trailing spaces in source files, which some IDEs trim automatically.
                buf.append("\n")
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

        if tok.type == "blockquote_open":
            # Blockquotes can contain multiple paragraphs and other blocks
            # We'll collect all inline content within the blockquote and combine them
            i += 1
            quote_content: List[dict] = []
            while i < len(tokens) and tokens[i].type != "blockquote_close":
                if tokens[i].type == "paragraph_open":
                    inline = tokens[i + 1] if i + 1 < len(tokens) and tokens[i + 1].type == "inline" else None
                    if inline:
                        # Add paragraph content to quote
                        paragraph_content = rich_from_inline(inline)
                        if quote_content and paragraph_content:
                            # Add a newline between paragraphs within the quote
                            quote_content.append({
                                "type": "text",
                                "text": {"content": "\n"},
                                "annotations": make_annotations(),
                            })
                        quote_content.extend(paragraph_content)
                    i += 3  # skip paragraph_open, inline, paragraph_close
                else:
                    i += 1
            # Add the complete quote block
            blocks.append({
                "type": "quote",
                "quote": {"rich_text": quote_content if quote_content else []},
            })
            # consume blockquote_close
            i += 1
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

        if tok.type == "code_block":
            # Indented code block (no explicit language)
            blocks.append({
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": tok.content.rstrip('\n')}}],
                    "language": "plain text",
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
