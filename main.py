#!/usr/bin/env python3

from typing import Optional, Sequence
import argparse

from notion_docs.cli import run, print_results, SUPPORTED_EXTENSIONS
from notion_docs.config import load_config


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Extract NOTION.* comments using YAML config")
    parser.add_argument("--config", "-c", default=".", help="Path to config file or directory (default: current directory)")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    results = run(cfg.root, SUPPORTED_EXTENSIONS)
    print_results(results, as_json=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

