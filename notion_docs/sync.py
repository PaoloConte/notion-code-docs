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
    source_files: List[str]


def _aggregate_comments(comments: List[BlockComment]) -> Dict[Tuple[str, ...], PageState]:
    # Combine texts for identical breadcrumbs in deterministic order (by file_path then text)
    logger.info("Aggregating %d comments by breadcrumb", len(comments))
    by_crumb: Dict[Tuple[str, ...], List[BlockComment]] = {}
    for c in comments:
        by_crumb.setdefault(tuple(c.breadcrumb), []).append(c)
    for lst in by_crumb.values():
        # Sort within the same breadcrumb by sort_index where None is treated as 1000 (default), then by file_path and text for stability
        lst.sort(key=lambda x: (x.sort_index if x.sort_index is not None else 1000, x.file_path))

    # Build a full set of breadcrumbs including all ancestors so that parents exist even if not directly documented
    crumbs_with_comments = set(by_crumb.keys())
    all_crumbs_set = set(crumbs_with_comments)
    for crumb in list(crumbs_with_comments):
        # add all prefixes (ancestors), excluding the empty root tuple
        for i in range(1, len(crumb)):
            all_crumbs_set.add(crumb[:i])

    # Prepare combined text for all crumbs; ancestors without direct comments get empty text
    combined_text: Dict[Tuple[str, ...], str] = {}
    source_files_by_crumb: Dict[Tuple[str, ...], List[str]] = {}
    for crumb in all_crumbs_set:
        if crumb in by_crumb:
            lst = by_crumb[crumb]
            combined_text[crumb] = "\n\n".join(c.text for c in lst)
            source_files_by_crumb[crumb] = [c.file_path for c in lst]
        else:
            combined_text[crumb] = ""
            source_files_by_crumb[crumb] = []

    combined_text_hash: Dict[Tuple[str, ...], str] = {
        crumb: hashlib.sha256(txt.encode("utf-8")).hexdigest()
        for crumb, txt in combined_text.items()
    }

    # Compute subtree hashes: for each crumb, SHA256 of newline-joined strict descendant combined text hashes
    subtree_hash: Dict[Tuple[str, ...], str] = {}
    all_crumbs = sorted(all_crumbs_set)
    for crumb in all_crumbs:
        descendant_hashes: List[Tuple[Tuple[str, ...], str]] = []
        for other, h in combined_text_hash.items():
            if len(crumb) < len(other) and list(crumb) == list(other[: len(crumb)]):
                descendant_hashes.append((other, h))
        descendant_hashes.sort(key=lambda x: x[0])
        joined = "\n".join(h for _, h in descendant_hashes)
        subtree_hash[crumb] = hashlib.sha256(joined.encode("utf-8")).hexdigest()

    logger.info("Aggregated into %d breadcrumbs (including ancestors)", len(all_crumbs))
    return {
        crumb: PageState(
            text=combined_text[crumb],
            text_hash=combined_text_hash[crumb],
            subtree_hash=subtree_hash[crumb],
            source_files=source_files_by_crumb.get(crumb, []),
        )
        for crumb in all_crumbs
    }




def sync_to_notion(config: AppConfig, comments: List[BlockComment], dry_run: bool = False, force: bool = False) -> None:
    """Sync aggregated comments to Notion under the configured root page.

    - One page per breadcrumb (segment path) under root_page_id.
    - Convert markdown to Notion blocks for the leaf's combined text.
    - Store metadata hashes in Notion page properties (Text Hash, Subtree Hash).
    - Only update a page if hashes changed, unless `force` is True.
    - When `force` is True, ignore hashes and update all pages and traverse all subpages.
    """
    logger.info(
        "Starting sync to Notion: %d comments -> root_page_id=%s (force=%s, dry_run=%s)",
        len(comments), getattr(config, 'root_page_id', ''), force, dry_run,
    )
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

    client = NotionClient(
        config.api_key,
        getattr(config, 'titles_matching', 'title_only'),
        getattr(config, 'header', None),
        getattr(config, 'include_file_in_header', False),
        getattr(config, 'quote_color', 'default'),
        getattr(config, 'inline_code_color', 'default'),
    )

    # Build children mapping for top-down traversal
    children: Dict[Tuple[str, ...], List[Tuple[str, ...]]] = {}
    for crumb in pages.keys():
        parent = crumb[:-1]
        children.setdefault(parent, []).append(crumb)
    for k in children.keys():
        children[k].sort()

    # Compute root subtree hash (hash of all top-level pages' subtree hashes)
    top_level_crumbs = sorted(children.get(tuple(), []))
    root_subtree_data = "\n".join(pages[crumb].subtree_hash for crumb in top_level_crumbs)
    root_subtree_hash = hashlib.sha256(root_subtree_data.encode("utf-8")).hexdigest()

    # Check root page hash first - skip everything if unchanged
    existing_root_text_hash, existing_root_subtree_hash = client.get_metadata(config.root_page_id)
    if not force and existing_root_subtree_hash == root_subtree_hash:
        logger.info("Root subtree unchanged, nothing to do")
        return

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
        child_crumbs = children.get(crumb, [])

        # Check which child pages need to be created (don't exist yet)
        new_children = []
        for child_crumb in child_crumbs:
            if child_crumb not in ensured:
                title = child_crumb[-1]
                existing_id = client.find_child_page(page_id, title)
                if existing_id:
                    ensured[child_crumb] = existing_id
                else:
                    new_children.append(child_crumb)

        # Check if we need to update content
        existing_text_hash, existing_subtree_hash = client.get_metadata(page_id)
        need_content = force or (existing_text_hash != state.text_hash) or bool(new_children)
        need_meta = force or (existing_text_hash != state.text_hash) or (existing_subtree_hash != state.subtree_hash)

        # Clear content FIRST, then create child pages, then append content
        # This ensures new child pages appear at the top (after existing child pages)
        if need_content:
            logger.info("Updating content for page '%s' (id=%s)", " / ".join(crumb), page_id)
            existing_children = client.clear_page_content(page_id)
            has_children = existing_children > 0 or bool(child_crumbs)
            # Now create new child pages (they will appear after existing child pages)
            for child_crumb in new_children:
                title = child_crumb[-1]
                child_id = client.create_child_page(page_id, title)
                ensured[child_crumb] = child_id
            # Append content after child pages
            client.append_page_content(page_id, state.text, state.source_files, has_children=has_children)
        else:
            logger.info("Content up-to-date for page '%s' (id=%s)", " / ".join(crumb), page_id)
        # Traverse children only if subtree hash changed, unless forcing
        if force or (existing_subtree_hash != state.subtree_hash):
            if force:
                logger.info("Force enabled; processing all subpages for '%s' (id=%s)", " / ".join(crumb), page_id)
            else:
                logger.info("Subtree changed for page '%s' (id=%s); processing subpages", " / ".join(crumb), page_id)
            for child_crumb in child_crumbs:
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
    for top in top_level_crumbs:
        process_node(config.root_page_id, top)

    # Update root page metadata
    logger.info("Updating root page metadata")
    client.set_metadata(config.root_page_id, "", root_subtree_hash)

    logger.info("Sync to Notion completed for %d pages", len(pages))
