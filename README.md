WARNING: this project has mostly been written by AI 😄

# What is this?
This python application scans block comments in code, containing a special tag, and transforms them into Notion pages. 

As example:
```kotlin
/* NOTION.Application 
 This application says hello
*/
fun main(args: Array<String>) {
    val name = "World"
    /*** NOTION.Application.Functions
     * # This is a comment
     * - and here a list
     * - with two items
     * */
    println("Hello, " + name + "!")
}
```

The first comment will generate a page named `Application` with the text "This application says hello".  
With the second comment, a page `Functions` will be created inside the `Application` page, containing the text 
`This is a comment` and a list with two items.


# Configuration
Use a config file named `notion-docs.yaml` (or `notion-docs.yml`).
```yaml
root: ./
root_page_id: YOUR_NOTION_ROOT_PAGE_ID
titles_matching: prefix
```
- `root` is the directory where the source code is located.
- `root_page_id` is the ID of the root page in Notion.
- `titles_matching` is the title matching strategy (all are case-insensitive). Possible values are:
  - `title_only` (default): matches the exact title of the page
  - `prefix`: matches the exact title of the page, or if it starts with the indicated prefix; useful if pages have a numbering or coding scheme; symbols are ignored 
  - `mnemonic`:  matches the exact title of the page, or if it starts with the computed mnemonic (see algorithm below)

Plus set an environment variable `NOTION_API_KEY` with the API key of your Notion connection.


### Mnemonic
To address pages, as an alternative to the exact page title, it's possible to use a mnemonic with a standardized format.
Here is how it is calculated:
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


# Setup
- create a private Notion connection and get the API key
- create a notion page and add the connection to id
- get the page ID and set it in the config file
- create properties `Subtree Hash` and `Text Hash`