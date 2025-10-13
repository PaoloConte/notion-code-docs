import re


def compute_mnemonic(title: str) -> str:
    """Compute a 3-character uppercase mnemonic from the given title.
    Rules:
    - Remove/ignore spaces and symbols; consider only alphanumeric characters.
    - First character: first alphanumeric char of the title, uppercased.
    - Next two characters: next consonant letters in order (Y counts as consonant).
    - If not enough consonants, use the next available alphanumeric characters starting from the second char.
    - If still fewer than 3 characters, pad with 'X'.
    """
    if not title:
        return "XXX"
    # Keep only ASCII letters and digits; drop spaces/symbols
    cleaned = re.sub(r"[^A-Za-z0-9]", "", title)
    if not cleaned:
        return "XXX"
    upper = cleaned.upper()
    first = upper[0]
    # Prepare lists for scanning after the first char
    rest = upper[1:]
    consonants = []
    others = []
    vowels = set("AEIOU")
    for ch in rest:
        if ch.isalpha():
            if ch not in vowels:  # treat Y as consonant
                consonants.append(ch)
            else:
                others.append(ch)
        elif ch.isdigit():
            others.append(ch)
        # ignore anything else (shouldn't exist after cleaning)
    result = [first]
    # Take up to two consonants
    while len(result) < 3 and consonants:
        result.append(consonants.pop(0))
    # If still short, take from others
    while len(result) < 3 and others:
        result.append(others.pop(0))
    # If still short, pad with 'X'
    while len(result) < 3:
        result.append('X')
    return "".join(result)
