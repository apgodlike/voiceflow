"""Tests for voiceflow.transcriber_parakeet — mocked onnx_asr, no model download."""
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

import voiceflow.transcriber_parakeet as tp


@pytest.fixture(autouse=True)
def reset_between_tests():
    tp.reset_model()
    yield
    tp.reset_model()


def _mock_onnx_asr(recognize_return="hello world"):
    model = MagicMock()
    model.recognize.return_value = recognize_return
    mod = MagicMock()
    mod.load_model.return_value = model
    return mod, model


def _patch_audio():
    # transcriber_parakeet imports soundfile lazily inside _read_audio
    sf = MagicMock()
    sf.read.return_value = (np.zeros(16000, dtype=np.float32), 16000)
    return patch.dict(sys.modules, {"soundfile": sf})


def test_not_loaded_initially():
    assert tp.is_loaded() is False


def test_transcribe_loads_and_returns_text(tmp_path):
    audio = tmp_path / "a.ogg"
    audio.write_bytes(b"\x00" * 100)
    mod, model = _mock_onnx_asr("  Hello there.  ")
    with patch.dict(sys.modules, {"onnx_asr": mod}), _patch_audio():
        out = tp.transcribe(audio)
    assert out == "Hello there."
    assert tp.is_loaded() is True
    model.recognize.assert_called_once()


def test_model_is_cached_across_calls(tmp_path):
    audio = tmp_path / "a.ogg"
    audio.write_bytes(b"\x00" * 100)
    mod, _ = _mock_onnx_asr()
    with patch.dict(sys.modules, {"onnx_asr": mod}), _patch_audio():
        tp.transcribe(audio)
        tp.transcribe(audio)
    mod.load_model.assert_called_once()  # loaded once, reused


def test_reset_model_forces_reload(tmp_path):
    audio = tmp_path / "a.ogg"
    audio.write_bytes(b"\x00" * 100)
    mod, _ = _mock_onnx_asr()
    with patch.dict(sys.modules, {"onnx_asr": mod}), _patch_audio():
        tp.transcribe(audio)
        tp.reset_model()
        assert tp.is_loaded() is False
        tp.transcribe(audio)
    assert mod.load_model.call_count == 2


def test_failure_wrapped_in_transcription_error(tmp_path):
    audio = tmp_path / "a.ogg"
    audio.write_bytes(b"\x00" * 100)
    mod, model = _mock_onnx_asr()
    model.recognize.side_effect = RuntimeError("boom")
    with patch.dict(sys.modules, {"onnx_asr": mod}), _patch_audio():
        with pytest.raises(tp.TranscriptionError):
            tp.transcribe(audio)


def test_missing_onnx_asr_raises_transcription_error(tmp_path):
    audio = tmp_path / "a.ogg"
    audio.write_bytes(b"\x00" * 100)
    # Simulate onnx_asr import failing
    with patch.dict(sys.modules, {"onnx_asr": None}):
        with pytest.raises(tp.TranscriptionError):
            tp.transcribe(audio)
