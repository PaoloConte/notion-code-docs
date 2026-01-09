# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python tool that extracts block comments tagged with `NOTION.*` from source code and syncs them as structured pages to Notion. It enables documentation-as-code by maintaining docs directly in source files.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python3 main.py --config notion-docs.yaml
python3 main.py --config . --force -v  # Force update all pages

# Run tests
pytest tests/
pytest tests/test_comments.py -v       # Single test file
pytest tests/ -k "test_normalize"      # Filter by name
```

## Architecture

**Data Flow:**
```
Source Files → Block Comment Extraction → Aggregation → Markdown Conversion → Notion Sync
```

**Core Modules (`notion_docs/`):**
- `files.py` - File discovery and comment extraction using Pygments lexers
- `comments.py` - Comment parsing, normalization, and NOTION tag extraction
- `sync.py` - Orchestrates sync with smart caching via SHA256 hashes
- `notion_api.py` - Notion API client with page matching strategies (exact, prefix, mnemonic)
- `markdown_to_notion.py` - Converts markdown to Notion block objects
- `config.py` - YAML configuration loading and validation

**Key Design Patterns:**
- Dual hashing (`text_hash` + `subtree_hash`) to only sync changed pages
- Comments with same breadcrumb from multiple files are aggregated
- `NOTION.*` placeholder reuses the previous breadcrumb in a file
- Sort indices (default 1000) control ordering within same parent

## Tag Syntax

```kotlin
/* NOTION.Page.Subpage
 * Content in markdown format
 */

/* NOTION[include_all].Features
 * Auto-includes following untagged comments
 */

/* NOTION.Page#2
 * Sort index 2 (lower = appears first)
 */
```

## Environment

- Requires `NOTION_API_KEY` environment variable
- Supported file extensions: `.java`, `.kt`, `.kts`, `.php`, `.md`