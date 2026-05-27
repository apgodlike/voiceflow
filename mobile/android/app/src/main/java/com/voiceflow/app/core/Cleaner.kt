package com.voiceflow.app.core

/**
 * Filler-word stripper + text normalizer.
 * 1:1 port of the desktop voiceflow/cleaner.py — pass order is not interchangeable.
 */
object Cleaner {
    private val FILLER_SIMPLE =
        Regex("\\b(?:you\\s+know|i\\s+mean|basically|uh+|um+|er+|ah+)\\b", RegexOption.IGNORE_CASE)
    private val TRAILING_RIGHT =
        Regex("\\bright\\b(?=\\s*[.,!?]|\\s*$)", RegexOption.IGNORE_CASE)

    // "like" as discourse filler only when preceded by a form of "to be";
    // group 1 captures the verb and is substituted back to preserve it.
    private val BE_LIKE =
        Regex("\\b(was|am|were|is|are|been|being|be)\\s+like\\b", RegexOption.IGNORE_CASE)

    private val LEADING_SO = Regex("^so\\s+", RegexOption.IGNORE_CASE)
    private val WHITESPACE = Regex("\\s+")
    private val SPACE_BEFORE_PUNCT = Regex("\\s+([.,!?;:])")
    private val LEADING_PUNCT = Regex("^[^\\w]+")

    fun clean(text: String): String {
        if (text.isEmpty()) return text

        var result = FILLER_SIMPLE.replace(text, "")
        result = TRAILING_RIGHT.replace(result, "")
        result = BE_LIKE.replace(result, "$1")

        result = WHITESPACE.replace(result, " ").trim()
        result = LEADING_SO.replace(result, "")
        result = LEADING_PUNCT.replace(result, "")

        result = WHITESPACE.replace(result, " ").trim()
        result = SPACE_BEFORE_PUNCT.replace(result, "$1")

        if (result.isEmpty()) return result

        result = result[0].uppercaseChar() + result.substring(1)
        if (result.last() !in charArrayOf('.', '!', '?')) result += "."

        return result
    }
}
