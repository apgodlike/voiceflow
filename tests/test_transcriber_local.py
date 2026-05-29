"""Tests for voiceflow.transcriber_local — uses mocks, no faster-whisper install needed."""
import builtins
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import voiceflow.transcriber_local as tl


@pytest.fixture(autouse=True)
def reset_between_tests():
    """Ensure each test starts with a clean module state."""
    tl.reset_model()
    yield
    tl.reset_model()


# ── is_loaded ──────────────────────────────────────────────────────────────


def test_is_loaded_false_before_any_call():
    assert tl.is_loaded() is False


def test_is_loaded_true_after_load(tmp_path):
    audio = tmp_path / "test.ogg"
    audio.write_bytes(b"\x00" * 100)

    mock_segment = MagicMock()
    mock_segment.text = "hello"
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], None)

    with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=lambda *a, **kw: mock_model)}):
        tl.transcribe(audio, model_name="base")

    assert tl.is_loaded() is True


# ── reset_model ────────────────────────────────────────────────────────────


def test_reset_model_clears_state(tmp_path):
    audio = tmp_path / "test.ogg"
    audio.write_bytes(b"\x00" * 100)

    mock_segment = MagicMock()
    mock_segment.text = "hi"
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment], None)

    with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=lambda *a, **kw: mock_model)}):
        tl.transcribe(audio, model_name="base")

    assert tl.is_loaded() is True
    tl.reset_model()
    assert tl.is_loaded() is False
    assert tl._model_name_loaded is None


# ── TranscriptionError on missing faster-whisper ───────────────────────────


def test_transcription_error_on_missing_package(tmp_path):
    audio = tmp_path / "test.ogg"
    audio.write_bytes(b"\x00" * 100)

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "faster_whisper":
            raise ImportError("No module named 'faster_whisper'")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        with pytest.raises(tl.TranscriptionError, match="faster-whisper not installed"):
            tl.transcribe(audio, model_name="base")


# ── transcribe returns stitched text ──────────────────────────────────────


def test_transcribe_stitches_segments(tmp_path):
    audio = tmp_path / "test.ogg"
    audio.write_bytes(b"\x00" * 100)

    seg1 = MagicMock()
    seg1.text = "Hello"
    seg2 = MagicMock()
    seg2.text = "world"
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([seg1, seg2], None)

    with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=lambda *a, **kw: mock_model)}):
        result = tl.transcribe(audio, model_name="tiny")

    assert result == "Hello world"


# ── transcribe wraps unexpected exceptions ────────────────────────────────


def test_transcribe_wraps_unexpected_error(tmp_path):
    audio = tmp_path / "test.ogg"
    audio.write_bytes(b"\x00" * 100)

    mock_model = MagicMock()
    mock_model.transcribe.side_effect = RuntimeError("GPU OOM")

    with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=lambda *a, **kw: mock_model)}):
        with pytest.raises(tl.TranscriptionError, match="Local transcription failed"):
            tl.transcribe(audio, model_name="base")


# ── infer_lock is held during transcribe ─────────────────────────────────


def test_infer_lock_serializes_calls(tmp_path):
    """transcribe() must acquire _infer_lock during inference."""
    audio = tmp_path / "test.ogg"
    audio.write_bytes(b"\x00" * 100)

    lock_held_during_call = []

    # Wrap _infer_lock in a spy that records acquisitions.
    class _SpyLock:
        def __init__(self, inner):
            self._inner = inner

        def __enter__(self):
            lock_held_during_call.append(True)
            return self._inner.__enter__()

        def __exit__(self, *args):
            return self._inner.__exit__(*args)

    spy = _SpyLock(threading.Lock())

    seg = MagicMock()
    seg.text = "ok"
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([seg], None)

    with patch.object(tl, "_infer_lock", spy):
        with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=lambda *a, **kw: mock_model)}):
            tl.transcribe(audio, model_name="base")

    assert lock_held_during_call, "_infer_lock was never acquired"
