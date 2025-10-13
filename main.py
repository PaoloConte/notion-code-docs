#!/usr/bin/env python3

from typing import Optional, Sequence
import argparse
import logging

from notion_docs.cli import run, SUPPORTED_EXTENSIONS
from notion_docs.config import load_config
from notion_docs.sync import sync_to_notion  # lazy import to avoid dependency in tests


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Extract NOTION.* comments and sync to Notion")
    parser.add_argument("--config", "-c", default=".", help="Path to config file or directory (default: current directory)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--log-level",
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"],
        help="Set logging level (overrides --verbose)."
    )
    args = parser.parse_args(argv)

    # Configure logging early
    if args.log_level:
        level = getattr(logging, args.log_level)
    else:
        level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s:%(name)s:%(message)s")

    cfg = load_config(args.config)
    results = run(cfg.root, SUPPORTED_EXTENSIONS)
    sync_to_notion(cfg, results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

