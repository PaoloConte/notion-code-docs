from pathlib import Path
from typing import List, Dict, Tuple
import hashlib

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
        /*
         * NOTION.A
         * Hello from A
         */
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
        /** NOTION.A.B C **/
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

    # Extract and collect by breadcrumb for stable assertions
    by_crumb: Dict[Tuple[str, ...], Tuple[str, str, str]] = {}
    for p in discovered:
        comments = extract_block_comments_from_file(p)
        for c in comments:
            by_crumb[tuple(c.breadcrumb)] = (c.text, c.text_hash, c.subtree_hash)

    # Only NOTION.* bodies should be present and normalized
    assert set(by_crumb.keys()) == {("A",), ("A", "B C")}

    # Validate hashes for each
    text_A, text_hash_A, subtree_hash_A = by_crumb[("A",)]
    assert text_A == "Hello from A"
    assert text_hash_A == hashlib.sha256(text_A.encode("utf-8")).hexdigest()

    text_BC, text_hash_BC, subtree_hash_BC = by_crumb[("A", "B C")]
    assert text_BC == "C"
    assert text_hash_BC == hashlib.sha256(text_BC.encode("utf-8")).hexdigest()

    # New subtree hash semantics: subtree hash is SHA-256 of newline-joined text hashes of strict descendants (excluding self)
    # For a leaf like A.B C, there are no descendants, so it's SHA-256 of an empty string
    expected_subtree_BC = hashlib.sha256(b"").hexdigest()
    assert subtree_hash_BC == expected_subtree_BC

    # With cross-file subtree, A should include its strict descendants across all files.
    # The only descendant is A.B C found in nested/B.kts, so subtree(A) = SHA256(text_hash_BC)
    expected_subtree_A = hashlib.sha256(text_hash_BC.encode("utf-8")).hexdigest()
    assert subtree_hash_A == expected_subtree_A





def test_duplicate_breadcrumb_texts_get_appended(tmp_path):
    root = Path(tmp_path)

    # File with parent A and one A.B entry
    write(
        root / "A.kt",
        (
            """
            /*
             * NOTION.A
             * Parent
             */
            /*
             * NOTION.A.B
             * Part1
             */
            val a = 0
            """
        ).strip(),
    )

    # Another file with two A.B entries
    write(
        root / "nested" / "B.kts",
        (
            """
            /*
             * NOTION.A.B
             * Part2
             */
            /*
             * NOTION.A.B
             * Part3
             */
            val b = 1
            """
        ).strip(),
    )

    discovered: List[str] = list(iter_source_files(str(root)))

    # Collect all comments
    all_comments = []
    for p in discovered:
        all_comments.extend(extract_block_comments_from_file(p))

    # Split by breadcrumb
    comments_A = [c for c in all_comments if tuple(c.breadcrumb) == ("A",)]
    comments_AB = [c for c in all_comments if tuple(c.breadcrumb) == ("A", "B")]

    # There should be one A and three A.B comments
    assert len(comments_A) == 1
    assert len(comments_AB) == 3

    # Check individual texts and hashes for A.B
    ab_texts = [c.text for c in comments_AB]
    assert ab_texts == ["Part1", "Part2", "Part3"]
    for c in comments_AB:
        assert c.text_hash == hashlib.sha256(c.text.encode("utf-8")).hexdigest()

    # Combined text for crumb (A,B) is appended with newlines in deterministic traversal order
    combined_ab_text = "\n".join(ab_texts)
    combined_ab_hash = hashlib.sha256(combined_ab_text.encode("utf-8")).hexdigest()

    # Subtree(A) should be the hash of the combined hash of its strict descendant (A,B)
    a = comments_A[0]
    expected_subtree_A = hashlib.sha256(combined_ab_hash.encode("utf-8")).hexdigest()
    assert a.subtree_hash == expected_subtree_A

    # A.B has no strict descendants, so subtree is empty-string hash
    empty_hash = hashlib.sha256(b"").hexdigest()
    for c in comments_AB:
        assert c.subtree_hash == empty_hash


def test_include_all_option_collects_subsequent_untagged_comments(tmp_path):
    """Test that NOTION[include_all] collects non-tagged comments after it."""
    root = Path(tmp_path)

    # File with include_all tag followed by regular comments
    write(
        root / "A.kt",
        """
        /*
         * NOTION[include_all].A
         * Tagged content
         */

        /* Regular comment 1 */

        /* Regular comment 2 */

        /*
         * NOTION.B
         * Another tagged content
         */

        /* Regular comment 3 */
        """.strip(),
    )

    discovered: List[str] = list(iter_source_files(str(root)))
    all_comments = []
    for p in discovered:
        all_comments.extend(extract_block_comments_from_file(p))

    # Should have two comments: A and B
    assert len(all_comments) == 2

    # Find A and B comments
    comment_A = next(c for c in all_comments if tuple(c.breadcrumb) == ("A",))
    comment_B = next(c for c in all_comments if tuple(c.breadcrumb) == ("B",))

    # A should include the tagged content plus the two regular comments after it
    assert "Tagged content" in comment_A.text
    assert "Regular comment 1" in comment_A.text
    assert "Regular comment 2" in comment_A.text
    assert "Regular comment 3" not in comment_A.text  # This comes after B

    # B should only have its own content (no include_all)
    assert comment_B.text == "Another tagged content"
    assert "Regular comment 3" not in comment_B.text

    # Verify options are set correctly
    assert comment_A.options == {"include_all": True}
    assert comment_B.options == {}


def test_include_all_with_multiple_tags(tmp_path):
    """Test include_all with multiple tags in the same file."""
    root = Path(tmp_path)

    write(
        root / "A.kt",
        """
        /*
         * NOTION[include_all].A
         * Content A
         */

        /* Comment for A */

        /*
         * NOTION[include_all].B
         * Content B
         */

        /* Comment for B */

        /*
         * NOTION.C
         * Content C
         */

        /* Comment after C */
        """.strip(),
    )

    discovered: List[str] = list(iter_source_files(str(root)))
    all_comments = []
    for p in discovered:
        all_comments.extend(extract_block_comments_from_file(p))

    # Should have three comments: A, B, C
    assert len(all_comments) == 3

    comment_A = next(c for c in all_comments if tuple(c.breadcrumb) == ("A",))
    comment_B = next(c for c in all_comments if tuple(c.breadcrumb) == ("B",))
    comment_C = next(c for c in all_comments if tuple(c.breadcrumb) == ("C",))

    # A should include its comment
    assert "Content A" in comment_A.text
    assert "Comment for A" in comment_A.text
    assert "Comment for B" not in comment_A.text

    # B should include its comment
    assert "Content B" in comment_B.text
    assert "Comment for B" in comment_B.text
    assert "Comment after C" not in comment_B.text

    # C should NOT include the comment after it (no include_all)
    assert comment_C.text == "Content C"
    assert "Comment after C" not in comment_C.text

