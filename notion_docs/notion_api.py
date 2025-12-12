import logging
from typing import List, Optional, Tuple
from notion_client import Client

logger = logging.getLogger(__name__)


from .markdown_to_notion import markdown_to_blocks
from .mnemonic import compute_mnemonic

class NotionClient:
    def __init__(self, api_key: str, titles_matching: str = "title_only", header: Optional[str] = None, include_files_in_header: bool = False, quote_color: str = "default", inline_code_color: str = "default"):
        self.client = Client(auth=api_key)
        self.titles_matching = (titles_matching or "title_only").lower()
        self.header = (header or "").strip() or None
        self.include_files_in_header = bool(include_files_in_header)
        self.quote_color = quote_color
        self.inline_code_color = inline_code_color


    def _markdown_to_blocks(self, md: str) -> List[dict]:
        """Delegate markdown conversion to the dedicated converter module."""
        return markdown_to_blocks(md, quote_color=self.quote_color, inline_code_color=self.inline_code_color)

    def _append_nested_blocks(self, parent_block_id: str, children: List[dict]) -> None:
        """Recursively append nested blocks to a parent block.
        Handles nested list items by extracting their children and appending separately."""
        for child_block in children:
            child_type = child_block.get("type")
            # Extract nested children if any (for list items)
            nested_children = child_block.pop("children", None)

            # Append the child block without its children
            resp = self.client.blocks.children.append(block_id=parent_block_id, children=[child_block])

            # If there are nested children, recursively append them
            if nested_children:
                created_block_id = resp.get("results", [{}])[0].get("id")
                if created_block_id:
                    self._append_nested_blocks(created_block_id, nested_children)

    def list_children(self, parent_block_id: str, page_size: int = 100) -> List[dict]:
        logger.info("Listing children for parent %s", parent_block_id)
        results: List[dict] = []
        start_cursor: Optional[str] = None
        while True:
            resp = self.client.blocks.children.list(block_id=parent_block_id, start_cursor=start_cursor, page_size=page_size)
            results.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            start_cursor = resp.get("next_cursor")
        logger.info("Found %d children under %s", len(results), parent_block_id)
        return results

    def find_child_page(self, parent_page_id: str, segment: str) -> Optional[str]:
        # For a page parent, the child pages appear as child_page blocks under the page's block children
        logger.info("Searching for child page matching segment '%s' under %s (mode=%s)", segment, parent_page_id, self.titles_matching)

        def norm(s: Optional[str]) -> str:
            # Remove symbols/spaces and casefold for prefix mode comparisons
            if not s:
                return ""
            import re
            return re.sub(r"[^A-Za-z0-9]", "", s).casefold()

        seg = segment or ""
        seg_cf = seg.casefold()
        seg_upper = seg.upper()
        seg_norm = norm(seg)

        for blk in self.list_children(parent_page_id):
            if blk.get("type") != "child_page":
                continue
            child = blk.get("child_page", {})
            title = child.get("title") or ""
            page_id = blk.get("id")

            mode = self.titles_matching

            if mode == "title_only":
                # Only exact case-insensitive title match
                if title.casefold() == seg_cf:
                    logger.info("Found child page by exact title '%s' (case-insensitive) with id %s", title, page_id)
                    return page_id
            elif mode == "mnemonic":
                # Match only if segment equals computed mnemonic (no exact title fallback)
                page_mn = compute_mnemonic(title)
                if page_mn == seg_upper:
                    logger.info("Found child page by computed mnemonic '%s' (title='%s') with id %s", page_mn, title, page_id)
                    return page_id
            elif mode == "prefix":
                # Match only if normalized title starts with normalized segment (symbols ignored, case-insensitive)
                # Do not match when the normalized segment equals the full normalized title (i.e., exact title)
                title_norm = norm(title)
                if seg_norm and title_norm.startswith(seg_norm) and title_norm != seg_norm:
                    logger.info("Found child page by prefix match: segment '%s' matches title '%s' (id=%s)", segment, title, page_id)
                    return page_id
            else:
                # Unknown mode: fallback to exact only behavior
                if title.casefold() == seg_cf:
                    logger.info("Found child page by exact title '%s' (case-insensitive, unknown mode) with id %s", title, page_id)
                    return page_id

        logger.info("Child page for segment '%s' not found under %s", segment, parent_page_id)
        return None

    def create_child_page(self, parent_page_id: str, title: str) -> str:
        logger.info("Creating child page '%s' under %s", title, parent_page_id)
        resp = self.client.pages.create(
            parent={"type": "page_id", "page_id": parent_page_id},
            properties={
                "title": [
                    {
                        "type": "text",
                        "text": {"content": title}
                    }
                ]
            },  # set page title
            icon=None,
            cover=None,
        )
        # The returned page has an "id"
        new_id = resp["id"]
        logger.info("Created page '%s' with id %s", title, new_id)
        return new_id

    def get_metadata(self, page_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Read metadata hashes from Notion page properties.
        Returns (text_hash, subtree_hash) or (None, None) if not present.
        """
        try:
            page = self.client.pages.retrieve(page_id=page_id)
            props = page.get("properties", {}) or {}

            def _get_prop_text(prop_name: str) -> Optional[str]:
                p = props.get(prop_name)
                if not p:
                    return None
                # We assume the property is of type 'rich_text' and only need text content
                if p.get("type") != "rich_text":
                    return None
                rts = p.get("rich_text", []) or []
                # Only extract the text type content (as assumed)
                text = "".join((rt.get("text", {}) or {}).get("content", "") for rt in rts)
                return text or None

            candidates_th = ["Text Hash", "text_hash"]
            candidates_sh = ["Subtree Hash", "subtree_hash"]
            th: Optional[str] = None
            sh: Optional[str] = None
            for name in candidates_th:
                th = _get_prop_text(name)
                if th:
                    break
            for name in candidates_sh:
                sh = _get_prop_text(name)
                if sh:
                    break
            logger.info("Metadata for %s -> text_hash=%s subtree_hash=%s", page_id, th, sh)
            return th, sh
        except Exception as e:
            logger.warning("Failed to read metadata for %s: %s", page_id, e)
            # If properties cannot be read, surface absence
            return None, None

    def set_metadata(self, page_id: str, text_hash: str, subtree_hash: str) -> None:
        """Write metadata via Notion page properties only."""
        logger.info("Setting metadata on %s", page_id)
        self.client.pages.update(
            page_id=page_id,
            properties={
                "Text Hash": {
                    "type": "rich_text",
                    "rich_text": [{"type": "text", "text": {"content": text_hash}}],
                },
                "Subtree Hash": {
                    "type": "rich_text",
                    "rich_text": [{"type": "text", "text": {"content": subtree_hash}}],
                },
            },
        )

    def replace_page_content(self, page_id: str, markdown_text: str, source_files: Optional[List[str]] = None) -> None:
        # Remove existing non-page children, then append markdown-converted blocks via official API
        logger.info("Replacing content on %s using official Notion API (md length=%d)", page_id, len(markdown_text) if markdown_text else 0)
        removed = 0
        skipped_child_pages = 0
        for blk in self.list_children(page_id):
            btype = blk.get("type")
            # Do NOT delete child pages or child databases; only remove content blocks
            if btype in {"child_page", "child_database"}:
                skipped_child_pages += 1
                continue
            self.client.blocks.delete(block_id=blk["id"])  # archive block
            removed += 1
        logger.info(
            "Removed %d blocks (skipped %d child pages/databases) from %s",
            removed,
            skipped_child_pages,
            page_id,
        )
        # Build new content blocks and append
        if markdown_text:
            blocks = self._markdown_to_blocks(markdown_text)
            # Prepend header callout if configured
            if self.header:
                header_text = self.header
                header_rich: List[dict] = [
                    {
                        "type": "text",
                        "text": {"content": header_text},
                        "annotations": {
                            "bold": False,
                            "italic": False,
                            "strikethrough": False,
                            "underline": False,
                            "code": False,
                            "color": "default",
                        },
                    }
                ]
                if self.include_files_in_header and source_files:
                    try:
                        # Show only basenames, unique and sorted for stability
                        import os
                        names = sorted({os.path.basename(s) for s in source_files if s})
                        if names:
                            # Add a new line with label
                            header_rich.append(
                                {
                                    "type": "text",
                                    "text": {"content": "\n"},
                                    "annotations": {
                                        "bold": False,
                                        "italic": False,
                                        "strikethrough": False,
                                        "underline": False,
                                        "code": False,
                                        "color": "default",
                                    },
                                }
                            )
                            # Add filenames as inline-code spans separated by comma+space
                            for i, nm in enumerate(names):
                                header_rich.append(
                                    {
                                        "type": "text",
                                        "text": {"content": nm},
                                        "annotations": {
                                            "bold": False,
                                            "italic": False,
                                            "strikethrough": False,
                                            "underline": False,
                                            "code": True,
                                            "color": "blue",
                                        },
                                    }
                                )
                                if i != len(names) - 1:
                                    header_rich.append(
                                        {
                                            "type": "text",
                                            "text": {"content": ", "},
                                            "annotations": {
                                                "bold": False,
                                                "italic": False,
                                                "strikethrough": False,
                                                "underline": False,
                                                "code": False,
                                                "color": "default",
                                            },
                                        }
                                    )
                    except Exception:
                        # Fail-safe: keep original header if anything goes wrong
                        pass
                header_block = {
                    "type": "callout",
                    "callout": {
                        "rich_text": header_rich,
                        "icon": {"type": "emoji", "emoji": "✨"},
                    },
                }
                # Add an empty paragraph after the callout when files are included
                empty_paragraph = {
                    "type": "paragraph",
                    "paragraph": {"rich_text": []},
                }
                blocks = [header_block, empty_paragraph] + blocks
            logger.info("Appending %d blocks to %s", len(blocks), page_id)
            # Append sequentially to properly handle table blocks (need to append rows under the created table)
            appended = 0
            for idx, block in enumerate(blocks):
                btype = block.get("type")
                if btype == "table":
                    # Extract table rows and embed them under table.children per API validation error
                    rows = block.pop("children", []) or []
                    tbl = block.get("table", {}) or {}
                    # Ensure table_width is at least 1 to satisfy API
                    width = int(tbl.get("table_width") or 0)
                    if width <= 0:
                        try:
                            width = max(1, max((len((r.get("table_row", {}) or {}).get("cells", [])) for r in rows), default=1))
                        except Exception:
                            width = 1
                        tbl["table_width"] = width
                    # Attach rows under table.children as required by the API
                    tbl["children"] = rows
                    block["table"] = tbl
                    # Append table with its rows in a single request
                    self.client.blocks.children.append(block_id=page_id, children=[block])
                    appended += 1
                elif btype == "bulleted_list_item":
                    # Handle nested list items: extract children and append separately
                    nested_children = block.pop("children", None)
                    # Append the parent list item without children
                    resp = self.client.blocks.children.append(block_id=page_id, children=[block])
                    appended += 1
                    # If there are nested children, append them to the newly created block
                    if nested_children:
                        created_block_id = resp.get("results", [{}])[0].get("id")
                        if created_block_id:
                            self._append_nested_blocks(created_block_id, nested_children)
                else:
                    # Append non-table blocks directly
                    self.client.blocks.children.append(block_id=page_id, children=[block])
                    appended += 1
            # Note: Official API doesn't provide reliable child block reordering across types; subpages may precede text.
            logger.info("Content appended to %s: %d top-level block(s) appended (tables handled with separate row appends)", page_id, appended)
