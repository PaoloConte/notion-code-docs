from pathlib import Path
import hashlib
import pytest

from notion_docs.files import extract_block_comments_from_file


def write(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_notion_star_uses_previous_breadcrumb(tmp_path, caplog):
    root = Path(tmp_path)
    p = root / "A.kt"
    write(
        p,
        (
            """
            /*
             * NOTION.A
             * Parent
             */
            /*
             * NOTION.*
             * Child
             */
            val x = 1
            """
        ).strip(),
    )

    caplog.set_level("ERROR", logger="notion_docs.files")

    comments = extract_block_comments_from_file(str(p))

    # Expect two comments under the same breadcrumb ("A",)
    a_comments = [c for c in comments if tuple(c.breadcrumb) == ("A",)]
    texts = [c.text for c in a_comments]
    assert texts == ["Parent", "Child"]

    # Ensure text_hashes are correct
    for c in a_comments:
        assert c.text_hash == hashlib.sha256(c.text.encode("utf-8")).hexdigest()

    # No error should be logged in this valid case
    assert not [rec for rec in caplog.records if rec.levelname == "ERROR"]


def test_notion_star_without_previous_logs_and_ignored(tmp_path, caplog):
    root = Path(tmp_path)
    p = root / "B.kt"
    write(
        p,
        (
            """
            /*
             * NOTION.*
             * Orphan
             */
            val y = 2
            """
        ).strip(),
    )

    caplog.set_level("ERROR", logger="notion_docs.files")

    comments = extract_block_comments_from_file(str(p))

    # The NOTION.* block should be ignored because there was no previous tag
    assert comments == []

    # An error should have been logged
    errors = [rec for rec in caplog.records if rec.levelname == "ERROR" and "NOTION.*" in rec.getMessage()]
    assert errors, "Expected an error log for leading NOTION.* placeholder"
