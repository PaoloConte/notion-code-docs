from notion_docs.comments import extract_block_comments_from_text


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
}
"""


def test_extract_block_comments_from_text_normalization():
    comments = extract_block_comments_from_text(SAMPLE_KOTLIN, lang="kotlin")
    bodies = [body for (_start, _end, body) in comments]

    assert len(bodies) == 5
    assert bodies[0] == "COMMENT 1"
    assert bodies[1] == "COMMENT 2"
    assert bodies[2] == "COMMENT 3\n - indented"
    assert bodies[3] == "COMMENT 4\n this is a comment"
    assert bodies[4] == "*COMMENT 5*\n - note"


