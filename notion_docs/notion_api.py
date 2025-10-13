import logging
from typing import List, Optional, Tuple
from notion_client import Client

logger = logging.getLogger(__name__)


from .markdown_to_notion import markdown_to_blocks
from .mnemonic import compute_mnemonic

class NotionClient:
    def __init__(self, api_key: str):
        self.client = Client(auth=api_key)


    def _markdown_to_blocks(self, md: str) -> List[dict]:
        """Delegate markdown conversion to the dedicated converter module."""
        return markdown_to_blocks(md)

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
        # Matching uses both the page title and the computed mnemonic, in a single pass.
        logger.info("Searching for child page matching segment '%s' under %s", segment, parent_page_id)
        segment_upper = (segment or "").upper()
        for blk in self.list_children(parent_page_id):
            if blk.get("type") == "child_page":
                child = blk.get("child_page", {})
                title = child.get("title")
                page_id = blk.get("id")
                # Check title match (case-insensitive) first
                if (title or "").casefold() == (segment or "").casefold():
                    logger.info("Found child page by title '%s' (case-insensitive) with id %s", title, page_id)
                    return page_id
                # If not title, check computed mnemonic match
                page_mn = compute_mnemonic(title or "")
                if page_mn == segment_upper:
                    logger.info("Found child page by computed mnemonic '%s' (title='%s') with id %s", page_mn, title, page_id)
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

    def replace_page_content(self, page_id: str, markdown_text: str) -> None:
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
                else:
                    # Append non-table blocks directly
                    self.client.blocks.children.append(block_id=page_id, children=[block])
                    appended += 1
            # Note: Official API doesn't provide reliable child block reordering across types; subpages may precede text.
            logger.info("Content appended to %s: %d top-level block(s) appended (tables handled with separate row appends)", page_id, appended)
