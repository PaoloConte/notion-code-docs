#!/usr/bin/env python3

from typing import Optional, Sequence

from notion_docs.cli import parse_args, run, print_results


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    results = run(args.root, args.ext)
    print_results(results, as_json=args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

