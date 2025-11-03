import pytest

from notion_docs.markdown_to_notion import markdown_to_blocks


def test_simple_blockquote():
    """Test basic blockquote conversion"""
    markdown = "> This is a quote"
    blocks = markdown_to_blocks(markdown)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "quote"
    assert len(blocks[0]["quote"]["rich_text"]) == 1
    assert blocks[0]["quote"]["rich_text"][0]["text"]["content"] == "This is a quote"


def test_blockquote_with_formatting():
    """Test blockquote with bold and italic text"""
    markdown = "> This is a **bold** and *italic* quote"
    blocks = markdown_to_blocks(markdown)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "quote"

    rich_text = blocks[0]["quote"]["rich_text"]
    # Should have multiple segments for: plain text, bold, plain text, italic, plain text
    assert len(rich_text) == 5

    # Check bold segment
    bold_segment = next((seg for seg in rich_text if seg["annotations"]["bold"]), None)
    assert bold_segment is not None
    assert bold_segment["text"]["content"] == "bold"

    # Check italic segment
    italic_segment = next((seg for seg in rich_text if seg["annotations"]["italic"]), None)
    assert italic_segment is not None
    assert italic_segment["text"]["content"] == "italic"


def test_multiline_blockquote():
    """Test blockquote with multiple lines"""
    markdown = "> This is the first line\n> This is the second line"
    blocks = markdown_to_blocks(markdown)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "quote"
    # Content should be combined
    content = blocks[0]["quote"]["rich_text"][0]["text"]["content"]
    assert "first line" in content and "second line" in content


def test_blockquote_with_multiple_paragraphs():
    """Test blockquote containing multiple paragraphs"""
    markdown = "> First paragraph\n>\n> Second paragraph"
    blocks = markdown_to_blocks(markdown)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "quote"

    rich_text = blocks[0]["quote"]["rich_text"]
    # Should have: first paragraph, newline separator, second paragraph
    assert len(rich_text) == 3
    assert rich_text[0]["text"]["content"] == "First paragraph"
    assert rich_text[1]["text"]["content"] == "\n"
    assert rich_text[2]["text"]["content"] == "Second paragraph"


def test_blockquote_with_inline_code():
    """Test blockquote containing inline code"""
    markdown = "> This has `code` in it"
    blocks = markdown_to_blocks(markdown)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "quote"

    rich_text = blocks[0]["quote"]["rich_text"]
    # Find the code segment
    code_segment = next((seg for seg in rich_text if seg["annotations"]["code"]), None)
    assert code_segment is not None
    assert code_segment["text"]["content"] == "code"


def test_mixed_content_with_blockquote():
    """Test that blockquotes work correctly alongside other block types"""
    markdown = "# Heading\n\nNormal paragraph\n\n> A quote\n\nAnother paragraph"
    blocks = markdown_to_blocks(markdown)

    assert len(blocks) == 4
    assert blocks[0]["type"] == "heading_1"
    assert blocks[1]["type"] == "paragraph"
    assert blocks[2]["type"] == "quote"
    assert blocks[3]["type"] == "paragraph"

    # Verify quote content
    assert blocks[2]["quote"]["rich_text"][0]["text"]["content"] == "A quote"


def test_empty_blockquote():
    """Test blockquote with no content"""
    markdown = ">"
    blocks = markdown_to_blocks(markdown)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "quote"
    assert blocks[0]["quote"]["rich_text"] == []


def test_blockquote_with_link():
    """Test blockquote containing a link"""
    markdown = "> This has a [link](https://example.com) in it"
    blocks = markdown_to_blocks(markdown)

    assert len(blocks) == 1
    assert blocks[0]["type"] == "quote"

    rich_text = blocks[0]["quote"]["rich_text"]
    # Find the linked segment
    link_segment = next((seg for seg in rich_text if seg.get("text", {}).get("link")), None)
    assert link_segment is not None
    assert link_segment["text"]["link"]["url"] == "https://example.com"
    assert link_segment["text"]["content"] == "link"