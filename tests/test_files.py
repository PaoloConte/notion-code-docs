from pathlib import Path
from typing import List

from notion_docs.files import iter_source_files, extract_block_comments_from_file


def write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_iter_and_extract_only_notion(tmp_path):
    root = Path(tmp_path)

    # File with both NOTION. and non-NOTION comments
    write(
        root / "A.kt",
        """
        /* NOTION.One */
        fun main() {
            /**
             * regular doc, ignored
             */
            println("hello")
        }
        """.strip(),
    )

    # Nested dir with another NOTION block (with stars and indentation)
    write(
        root / "nested" / "B.kts",
        """
        /**
         *   NOTION.Two
         */
        val x = 1
        """.strip(),
    )

    # File with only non-NOTION comments (should yield none)
    write(
        root / "C.kt",
        """
        /*** regular ***/
        /* another one */
        val y = 2
        """.strip(),
    )

    # Discover files
    discovered: List[str] = list(iter_source_files(str(root)))
    assert any(p.endswith("A.kt") for p in discovered)
    assert any(p.endswith("B.kts") for p in discovered)
    assert any(p.endswith("C.kt") for p in discovered)

    # Extract and collect comment texts; filter is applied inside extract_block_comments_from_file
    texts = []
    for p in discovered:
        comments = extract_block_comments_from_file(p)
        texts.extend([c.text for c in comments])

    # Only NOTION.* bodies should be present and normalized
    assert sorted(texts) == ["NOTION.One", "NOTION.Two"]


