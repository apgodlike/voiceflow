"""Tests for voiceflow.ai_cleanup — mocked providers; the key invariant is
*fail open* (never lose a dictation)."""
import sys
from unittest.mock import MagicMock, patch

import voiceflow.ai_cleanup as ac

LONG = "this is a reasonably long transcript that should survive cleanup"


def test_disabled_returns_original():
    assert ac.refine(LONG, {"ai_cleanup": False}) == LONG


def test_empty_text_returns_original():
    assert ac.refine("   ", {"ai_cleanup": True}) == "   "


def test_ollama_success():
    resp = MagicMock()
    resp.json.return_value = {"response": "This is a clean transcript that survived cleanup."}
    resp.raise_for_status.return_value = None
    req = MagicMock()
    req.post.return_value = resp
    with patch.dict(sys.modules, {"requests": req}):
        out = ac.refine(LONG, {"ai_cleanup": True, "ai_cleanup_provider": "ollama"})
    assert out == "This is a clean transcript that survived cleanup."
    req.post.assert_called_once()


def test_ollama_failure_fails_open():
    req = MagicMock()
    req.post.side_effect = RuntimeError("connection refused")
    with patch.dict(sys.modules, {"requests": req}):
        out = ac.refine(LONG, {"ai_cleanup": True, "ai_cleanup_provider": "ollama"})
    assert out == LONG  # original returned, not lost


def test_suspiciously_short_result_is_rejected():
    resp = MagicMock()
    resp.json.return_value = {"response": "ok"}  # way shorter than input
    resp.raise_for_status.return_value = None
    req = MagicMock()
    req.post.return_value = resp
    with patch.dict(sys.modules, {"requests": req}):
        out = ac.refine(LONG, {"ai_cleanup": True, "ai_cleanup_provider": "ollama"})
    assert out == LONG


def test_openai_missing_key_fails_open(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    out = ac.refine(LONG, {"ai_cleanup": True, "ai_cleanup_provider": "openai",
                           "openai_api_key": ""})
    assert out == LONG
