import hashlib
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from .notion_api import NotionClient  

from .models import BlockComment
from .config import AppConfig

logger = logging.getLogger(__name__)


@dataclass
class PageState:
    text: str
    text_hash: str
    subtree_hash: str


def _aggregate_comments(comments: List[BlockComment]) -> Dict[Tuple[str, ...], PageState]:
    # Combine texts for identical breadcrumbs in deterministic order (by file_path then text)
    logger.info("Aggregating %d comments by breadcrumb", len(comments))
    by_crumb: Dict[Tuple[str, ...], List[BlockComment]] = {}
    for c in comments:
        by_crumb.setdefault(tuple(c.breadcrumb), []).append(c)
    for lst in by_crumb.values():
        lst.sort(key=lambda x: (x.file_path, x.text))

    combined_text: Dict[Tuple[str, ...], str] = {
        crumb: "\n\n".join(c.text for c in lst) for crumb, lst in by_crumb.items()
    }
    combined_text_hash: Dict[Tuple[str, ...], str] = {
        crumb: hashlib.sha256(txt.encode("utf-8")).hexdigest()
        for crumb, txt in combined_text.items()
    }

    # Compute subtree hashes: for each crumb, SHA256 of newline-joined strict descendant combined text hashes
    subtree_hash: Dict[Tuple[str, ...], str] = {}
    all_crumbs = sorted(combined_text_hash.keys())
    for crumb in all_crumbs:
        descendant_hashes: List[Tuple[Tuple[str, ...], str]] = []
        for other, h in combined_text_hash.items():
            if len(crumb) < len(other) and list(crumb) == list(other[: len(crumb)]):
                descendant_hashes.append((other, h))
        descendant_hashes.sort(key=lambda x: x[0])
        joined = "\n".join(h for _, h in descendant_hashes)
        subtree_hash[crumb] = hashlib.sha256(joined.encode("utf-8")).hexdigest()

    logger.info("Aggregated into %d breadcrumbs", len(all_crumbs))
    return {
        crumb: PageState(text=combined_text[crumb], text_hash=combined_text_hash[crumb], subtree_hash=subtree_hash[crumb])
        for crumb in all_crumbs
    }




def sync_to_notion(config: AppConfig, comments: List[BlockComment], dry_run: bool = False) -> None:
    """Sync aggregated comments to Notion under the configured root page.

    - One page per breadcrumb (segment path) under root_page_id.
    - Convert markdown to Notion blocks for the leaf's combined text.
    - Store metadata hashes in Notion page properties (Text Hash, Subtree Hash).
    - Only update a page if hashes changed.
    """
    logger.info("Starting sync to Notion: %d comments -> root_page_id=%s", len(comments), getattr(config, 'root_page_id', ''))
    pages = _aggregate_comments(comments)
    if not pages:
        logger.info("No pages to sync (no comments after aggregation). Nothing to do.")
        return

    if dry_run:
        # No side effects, but still compute aggregation (useful for debugging)
        logger.info("Dry run enabled: would sync %d pages", len(pages))
        for crumb in sorted(pages.keys()):
            logger.info("[DRY RUN] Would ensure page: %s", " / ".join(crumb))
        return

    client = NotionClient(config.api_key)

    # Build children mapping for top-down traversal
    children: Dict[Tuple[str, ...], List[Tuple[str, ...]]] = {}
    for crumb in pages.keys():
        parent = crumb[:-1]
        children.setdefault(parent, []).append(crumb)
    for k in children.keys():
        children[k].sort()

    ensured: Dict[Tuple[str, ...], str] = {tuple(): config.root_page_id}

    def ensure_page(parent_id: str, crumb: Tuple[str, ...]) -> str:
        title = crumb[-1]
        logger.info("Ensuring page for crumb '%s' (parent path len=%d)", title, len(crumb) - 1)
        child_id = client.find_child_page(parent_id, title)
        if not child_id:
            logger.info("Page '%s' not found under parent %s, creating it", title, parent_id)
            child_id = client.create_child_page(parent_id, title)
        logger.info("Ensured page '%s' -> id=%s", " / ".join(crumb), child_id)
        return child_id

    def process_node(parent_id: str, crumb: Tuple[str, ...]) -> None:
        # Ensure current page exists
        page_id = ensured.get(crumb)
        if not page_id:
            page_id = ensure_page(parent_id, crumb)
            ensured[crumb] = page_id
        state = pages[crumb]
        # Update current page content first
        existing_text_hash, existing_subtree_hash = client.get_metadata(page_id)
        need_content = existing_text_hash != state.text_hash
        need_meta = (existing_text_hash != state.text_hash) or (existing_subtree_hash != state.subtree_hash)
        if need_content:
            logger.info("Updating content for page '%s' (id=%s)", " / ".join(crumb), page_id)
            client.replace_page_content(page_id, state.text)
        else:
            logger.info("Content up-to-date for page '%s' (id=%s)", " / ".join(crumb), page_id)
        # Traverse children only if subtree hash changed
        if existing_subtree_hash != state.subtree_hash:
            logger.info("Subtree changed for page '%s' (id=%s); processing subpages", " / ".join(crumb), page_id)
            for child_crumb in children.get(crumb, []):
                process_node(page_id, child_crumb)
        else:
            logger.info("Subtree unchanged for page '%s' (id=%s); skipping checks/ensures for subpages", " / ".join(crumb), page_id)
        # After updating content and any subpages, update metadata if needed
        if need_meta:
            logger.info("Updating metadata for page '%s' (id=%s) after subtree update", " / ".join(crumb), page_id)
            client.set_metadata(page_id, state.text_hash, state.subtree_hash)
        else:
            logger.info("Metadata up-to-date for page '%s' (id=%s)", " / ".join(crumb), page_id)

    # Start from top-level crumbs under the configured root
    for top in sorted(children.get(tuple(), [])):
        process_node(config.root_page_id, top)

    logger.info("Sync to Notion completed for %d pages", len(pages))
