from notion_docs.comments import extract_block_comments_from_text, parse_breadcrumb_and_strip


SAMPLE_KOTLIN = """
/* COMMENT 1 */
fun main() {
    val name = "Kotlin"
    /*** COMMENT 2 */
    println("Hello, " + name + "!")

    /*
        COMMENT 3
         - indented
     */
    for (i in 1..5) {
        /**
         * COMMENT 4
         *  this is a comment
         */
        println("i = $i")
    }
    /**
     * *COMMENT 5*
     *  - note
     */
     
/** NOTION.FTR.AVS

    ### API
    Text
**/

/** NOTION.FTR.AVS
 *
 *  ### API
 *  Text
**/

    /** NOTION.INT.DPL
     * ### Title
     *
     * Text
     */
     
     
    /** NOTION.INT.DPL
        ### Aligned
     
        Text
     */
     
     
    /** 
        NOTION.INT.DPL
        ### Aligned
     
        Text
     */

    /** 
     * NOTION.INT.DPL
     * ### Title
     *
     * Text
     */
     
     /* NOTION.A.B  Comment 123 */
     
}
"""


def test_extract_block_comments_from_text_normalization():
    bodies = extract_block_comments_from_text(SAMPLE_KOTLIN, lang="kotlin")

    assert len(bodies) == 12
    assert bodies[0] == "COMMENT 1"
    assert bodies[1] == "COMMENT 2"
    assert bodies[2] == "COMMENT 3\n - indented"
    assert bodies[3] == "COMMENT 4\n this is a comment"
    assert bodies[4] == "*COMMENT 5*\n - note"
    assert bodies[5] == "NOTION.FTR.AVS\n\n### API\nText"
    assert bodies[6] == "NOTION.FTR.AVS\n\n### API\nText"
    assert bodies[7] == "NOTION.INT.DPL\n### Title\n\nText"
    assert bodies[8] == "NOTION.INT.DPL\n### Aligned\n\nText"
    assert bodies[9] == "NOTION.INT.DPL\n### Aligned\n\nText"
    assert bodies[10] == "NOTION.INT.DPL\n### Title\n\nText"
    assert bodies[11] == "NOTION.A.B  Comment 123"


def test_parse_breadcrumb_and_strip():
    cases = [
        ("NOTION.A.B.C Remaining text", (["A", "B", "C"], "Remaining text")),
        ("NOTION.A Title\nBody", (["A", "Title"], "Body")),
        ("NOTION.A.B C\nMore", (["A", "B C"], "More")),
        ("NOTION.* Comment", (["*"], "Comment")),
        ("No prefix", None),
    ]
    for body, expected in cases:
        result = parse_breadcrumb_and_strip(body)
        assert result == expected



