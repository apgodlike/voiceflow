"""Filler word stripper + text normalizer."""
import argparse
import re

_FILLER_SIMPLE = re.compile(
    r"\b(?:you\s+know|i\s+mean|basically|uh+|um+|er+|ah+)\b",
    re.IGNORECASE,
)
_TRAILING_RIGHT = re.compile(r"\bright\b(?=\s*[.,!?]|\s*$)", re.IGNORECASE)

# "like" as discourse filler only when preceded by a form of "to be"
# e.g. "I was like going" → "I was going"; but "I like coffee" → unchanged
_BE_LIKE = re.compile(
    r"\b(was|am|were|is|are|been|being|be)\s+like\b", re.IGNORECASE
)

# "so" at sentence start — applied after whitespace normalization so ^ works
_LEADING_SO = re.compile(r"^so\s+", re.IGNORECASE)

_WHITESPACE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,!?;:])")
_LEADING_PUNCT = re.compile(r"^[^\w]+")


def clean(text: str) -> str:
    if not text:
        return text

    result = _FILLER_SIMPLE.sub("", text)
    result = _TRAILING_RIGHT.sub("", result)
    result = _BE_LIKE.sub(r"\1", result)

    # normalize whitespace before sentence-start checks
    result = _WHITESPACE.sub(" ", result).strip()
    result = _LEADING_SO.sub("", result)
    result = _LEADING_PUNCT.sub("", result)

    result = _WHITESPACE.sub(" ", result).strip()
    result = _SPACE_BEFORE_PUNCT.sub(r"\1", result)

    if not result:
        return result

    result = result[0].upper() + result[1:]
    if result[-1] not in ".!?":
        result += "."

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    args = parser.parse_args()
    print(clean(args.text))
