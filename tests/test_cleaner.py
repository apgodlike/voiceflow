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
