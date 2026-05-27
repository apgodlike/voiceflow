"""Tests for cleaner.py — table-driven filler stripping."""
import pytest
from voiceflow.cleaner import clean

CASES = [
    # (input, expected)
    ("", ""),
    ("um hello world", "Hello world."),
    # "like" used as discourse filler after "was" — stripped
    ("uh so basically i was like you know going to the store right", "I was going to the store."),
    # "like" used as main verb — kept
    ("I like coffee", "I like coffee."),
    # "feel like" — not a "to be" form but keep as-is (not stripped)
    ("I feel like going out", "I feel like going out."),
    ("I sound like a robot", "I sound like a robot."),
    # all fillers — "what" is real word, stays
    ("you know what i mean basically", "What."),
    ("Hello world.", "Hello world."),
    ("hello world", "Hello world."),
    # trailing "right" before ? and .
    ("That is great right?", "That is great?"),
    ("That is great right.", "That is great."),
    # only fillers — result is empty string
    ("um um um", ""),
    # leading "so" stripped
    ("So I went to the store", "I went to the store."),
    # leading fillers leave leading comma — cleaned
    ("er ah, I was thinking", "I was thinking."),
]

@pytest.mark.parametrize("text,expected", CASES)
def test_clean(text, expected):
    assert clean(text) == expected


# ── custom dictionary ──────────────────────────────────────────────────────

def test_dictionary_basic_replacement():
    assert clean("i love cloud code", dictionary={"cloud": "Claude"}) == "I love Claude code."


def test_dictionary_case_insensitive_match_verbatim_target():
    assert clean("Cloud is great", dictionary={"cloud": "Claude"}) == "Claude is great."


def test_dictionary_multiword_phrase():
    assert clean("i use open ai daily", dictionary={"open ai": "OpenAI"}) == "I use OpenAI daily."


def test_dictionary_longest_key_wins():
    d = {"new york": "NYC", "york": "York"}
    assert clean("i live in new york", dictionary=d) == "I live in NYC."


def test_dictionary_word_ending_in_b_not_mangled():
    # guards the earlier strip("\\b") bug — "club" must survive untouched
    assert clean("at the club tonight", dictionary={"foo": "bar"}) == "At the club tonight."


def test_dictionary_replacement_with_backslash_digit_is_literal():
    assert clean("see item one", dictionary={"item one": r"\1 item"}) == r"See \1 item."


# ── extra fillers ──────────────────────────────────────────────────────────

def test_extra_fillers_stripped():
    assert clean("kinda hello world", extra_fillers=["kinda"]) == "Hello world."


def test_extra_filler_multiword():
    assert clean("sort of done here", extra_fillers=["sort of"]) == "Done here."


def test_builtin_fillers_still_work_with_extras():
    assert clean("um kinda hello", extra_fillers=["kinda"]) == "Hello."


# ── voice commands (opt-in) ────────────────────────────────────────────────

def test_voice_commands_off_by_default():
    assert clean("hello comma world") == "Hello comma world."


def test_voice_command_comma():
    assert clean("hello comma world", voice_commands=True) == "Hello, world."


def test_voice_command_period_terminates():
    assert clean("done period", voice_commands=True) == "Done."


def test_voice_command_question_mark():
    assert clean("really question mark", voice_commands=True) == "Really?"


def test_voice_command_new_line():
    assert clean("line one new line line two", voice_commands=True) == "Line one\nline two."


def test_voice_command_new_paragraph():
    assert clean("para one new paragraph para two", voice_commands=True) == "Para one\n\npara two."


def test_voice_command_trailing_newline_no_period_appended():
    assert clean("hello new line", voice_commands=True) == "Hello"


def test_voice_command_paragraph_beats_line():
    # "new paragraph" must not be partially matched as "new line"
    assert clean("a new paragraph b", voice_commands=True) == "A\n\nb."
