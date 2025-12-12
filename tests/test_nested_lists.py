import pytest

from notion_docs.markdown_to_notion import markdown_to_blocks


def test_nested_bullet_lists():
    """Test nested bullet list conversion with standard markdown spacing (4 spaces per level)"""
    # Using explicit line breaks to make indentation clear
    markdown = (
        "- First level item 1\n"
        "    - Second level item 1\n"
        "    - Second level item 2\n"
        "- First level item 2\n"
        "    - Second level item 3\n"
        "        - Third level item 1"
    )

    blocks = markdown_to_blocks(markdown)

    # Should have 2 top-level list items
    assert len(blocks) == 2
    assert all(b["type"] == "bulleted_list_item" for b in blocks)

    # Check first top-level item
    assert blocks[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "First level item 1"
    assert "children" in blocks[0]
    assert len(blocks[0]["children"]) == 2
    assert blocks[0]["children"][0]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "Second level item 1"
    assert blocks[0]["children"][1]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "Second level item 2"

    # Check second top-level item
    assert blocks[1]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "First level item 2"
    assert "children" in blocks[1]
    assert len(blocks[1]["children"]) == 1

    # Check nested third level
    second_level_item = blocks[1]["children"][0]
    assert second_level_item["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "Second level item 3"
    assert "children" in second_level_item
    assert len(second_level_item["children"]) == 1
    assert second_level_item["children"][0]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "Third level item 1"


def test_simple_nested_list():
    """Test a simple two-level nested list"""
    markdown = (
        "- Parent item\n"
        "    - Child item 1\n"
        "    - Child item 2"
    )

    blocks = markdown_to_blocks(markdown)

    # Should have 1 top-level list item with 2 children
    assert len(blocks) == 1
    assert blocks[0]["type"] == "bulleted_list_item"
    assert blocks[0]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "Parent item"

    # Check children
    assert "children" in blocks[0]
    assert len(blocks[0]["children"]) == 2
    assert blocks[0]["children"][0]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "Child item 1"
    assert blocks[0]["children"][1]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "Child item 2"


def test_mixed_content_with_nested_lists():
    """Test nested lists with other formatting"""
    markdown = (
        "- Item with **bold**\n"
        "    - Nested item with *italic*\n"
        "    - Another nested item\n"
        "- Second top-level item"
    )

    blocks = markdown_to_blocks(markdown)

    # Should have 2 top-level items
    assert len(blocks) == 2
    assert all(b["type"] == "bulleted_list_item" for b in blocks)

    # Check first item has bold text and nested children
    first_item = blocks[0]
    rich_text = first_item["bulleted_list_item"]["rich_text"]

    # Find the bold segment
    bold_segment = next((seg for seg in rich_text if seg["annotations"]["bold"]), None)
    assert bold_segment is not None
    assert bold_segment["text"]["content"] == "bold"

    # Check nested items
    assert "children" in first_item
    assert len(first_item["children"]) == 2

    # Check first nested item has italic
    nested_item_1 = first_item["children"][0]
    nested_rich_text = nested_item_1["bulleted_list_item"]["rich_text"]
    italic_segment = next((seg for seg in nested_rich_text if seg["annotations"]["italic"]), None)
    assert italic_segment is not None
    assert italic_segment["text"]["content"] == "italic"

    # Check second nested item
    nested_item_2 = first_item["children"][1]
    assert nested_item_2["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "Another nested item"

    # Check second top-level item has no children
    assert blocks[1]["bulleted_list_item"]["rich_text"][0]["text"]["content"] == "Second top-level item"
    assert "children" not in blocks[1]