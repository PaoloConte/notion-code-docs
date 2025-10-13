# Setup [Draft]
- create a private Notion connection and get the API key
- create a notion page and add the connection to id
- get the page ID and set it in the config file
- create properties `Subtree Hash` and `Text Hash`

## Mnemonic
To address pages, as an alternative to the exact page title, it's possible to use a mnemonic with a standardized format.
Here is how to calculate it:
- Ignore spaces and symbols.
- Three uppercase letters or numbers.
- The first letter of the code is the first letter of the title.
- The following two characters are the next to consonants of the word.
- If not enough consonants are available, use the vowels starting from the beginning.
- If the title is to short, the missing characters are replaced with `X`.

Examples:
- "Alpha Beta Gamma" → ALP
- "Echo" → ECH
- "why" → WHY
- "Idea 123" → IDE
- "A1" → A1X
- "C# Sharp Developer" → CSH
- "123abc" → 1BC
- "!!!" → XXX