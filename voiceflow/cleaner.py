"""Filler word stripper + text normalizer.

``clean(text)`` keeps its original zero-config behavior. Three optional,
config-driven refinements layer on top via keyword args:

* ``dictionary``    — phrase/word replacement map (fix mistranscribed names).
* ``extra_fillers`` — extra filler words to strip alongside the built-ins.
* ``voice_commands``— opt-in: spoken punctuation ("comma", "new line", …)
  turned into the literal symbol. Off by default to avoid false positives.
"""
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

# Sentinels for newline commands — survive whitespace collapse (no \s chars),
# restored to real newlines at the very end.
_NL = "\x00NL\x00"
_PARA = "\x00PARA\x00"

# Spoken → literal. Order matters: longer/multi-word phrases first so e.g.
# "new paragraph" wins over "new line". Punctuation inserts inline (the
# space-before-punct pass tidies spacing); newlines go through sentinels.
_VOICE_COMMANDS: list[tuple[str, str]] = [
    ("new paragraph", _PARA),
    ("new line", _NL),
    ("exclamation mark", "!"),
    ("exclamation point", "!"),
    ("question mark", "?"),
    ("full stop", "."),
    ("semicolon", ";"),
    ("period", "."),
    ("comma", ","),
    ("colon", ":"),
]


def _phrase_inner(phrase: str) -> str:
    """Escaped phrase core (no boundaries), tolerant of varied inter-word spacing."""
    return r"\s+".join(re.escape(w) for w in phrase.split())


def _phrase_pattern(phrase: str) -> str:
    """Word-boundary regex for a phrase."""
    return r"\b" + _phrase_inner(phrase) + r"\b"


def _apply_dictionary(text: str, dictionary: dict[str, str]) -> str:
    # Longest keys first so multi-word entries aren't pre-empted by their parts.
    for key in sorted(dictionary, key=len, reverse=True):
        value = dictionary[key]
        if not key.strip():
            continue
        text = re.sub(
            _phrase_pattern(key),
            lambda _m, v=value: v,  # lambda avoids backref issues if v has \1 etc.
            text,
            flags=re.IGNORECASE,
        )
    return text


def _apply_voice_commands(text: str) -> str:
    for phrase, repl in _VOICE_COMMANDS:
        text = re.sub(_phrase_pattern(phrase), repl, text, flags=re.IGNORECASE)
    return text


def _filler_pattern(extra_fillers: list[str] | None) -> re.Pattern:
    if not extra_fillers:
        return _FILLER_SIMPLE
    extra = "|".join(_phrase_inner(f) for f in extra_fillers if f.strip())
    if not extra:
        return _FILLER_SIMPLE
    return re.compile(
        r"\b(?:you\s+know|i\s+mean|basically|uh+|um+|er+|ah+|" + extra + r")\b",
        re.IGNORECASE,
    )


def clean(
    text: str,
    *,
    dictionary: dict[str, str] | None = None,
    extra_fillers: list[str] | None = None,
    voice_commands: bool = False,
) -> str:
    if not text:
        return text

    result = text
    if dictionary:
        result = _apply_dictionary(result, dictionary)
    if voice_commands:
        result = _apply_voice_commands(result)

    result = _filler_pattern(extra_fillers).sub("", result)
    result = _TRAILING_RIGHT.sub("", result)
    result = _BE_LIKE.sub(r"\1", result)

    # normalize whitespace before sentence-start checks (sentinels survive — no \s)
    result = _WHITESPACE.sub(" ", result).strip()
    result = _LEADING_SO.sub("", result)
    result = _LEADING_PUNCT.sub("", result)

    result = _WHITESPACE.sub(" ", result).strip()
    result = _SPACE_BEFORE_PUNCT.sub(r"\1", result)

    if not result:
        return result

    # Capitalize/terminal-punct ignoring any trailing newline sentinel.
    ends_with_newline = result.endswith(_NL) or result.endswith(_PARA)
    result = result[0].upper() + result[1:]
    if not ends_with_newline and result[-1] not in ".!?":
        result += "."

    # Restore newlines last; trim spaces hugging the sentinels.
    result = re.sub(r"\s*" + re.escape(_PARA) + r"\s*", "\n\n", result)
    result = re.sub(r"\s*" + re.escape(_NL) + r"\s*", "\n", result)

    return result.strip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--voice-commands", action="store_true")
    args = parser.parse_args()
    print(clean(args.text, voice_commands=args.voice_commands))
