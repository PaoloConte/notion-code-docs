import pytest

from notion_docs.mnemonic import compute_mnemonic


@pytest.mark.parametrize(
    "title, expected",
    [
        # Basic: pick first letter + next two consonants
        ("Alpha Beta Gamma", "ALP"),  # A + (L,P)
        ("Echo", "ECH"),               # E + (C,H)
        # Y is a consonant
        ("why", "WHY"),
        # Use others (vowels/digits) when not enough consonants
        ("Idea 123", "IDE"),  # I + D + next available (E)
        ("A1", "A1X"),        # A + 1 + pad X
        # Empty and symbols-only fall back to XXX
        ("", "XXX"),
        ("!!!", "XXX"),
        # Remove symbols/spaces
        ("C# Sharp Developer", "CSH"),  # C + (S,H)
        # Title starting with a digit
        ("123abc", "1BC"),
    ],
)
def test_compute_mnemonic(title: str, expected: str):
    assert compute_mnemonic(title) == expected
