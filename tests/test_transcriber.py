"""Tests for transcriber.py — monkeypatched OpenAI client."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from voiceflow import transcriber
from voiceflow.transcriber import TranscriptionError, transcribe


@pytest.fixture(autouse=True)
def _reset_client():
    """The module caches the OpenAI client; clear it so each test's patched
    OpenAI is the one that gets built."""
    transcriber.reset_client()
    yield
    transcriber.reset_client()


def test_client_reused_across_calls(tmp_path):
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 36)
    mock_response = MagicMock(text="hi")
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = mock_response

    with patch("voiceflow.transcriber.OpenAI", return_value=mock_client) as factory:
        transcribe(wav)
        transcribe(wav)

    factory.assert_called_once()  # one client built, reused for both calls


def test_reset_client_rebuilds(tmp_path):
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 36)
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = MagicMock(text="hi")

    with patch("voiceflow.transcriber.OpenAI", return_value=mock_client) as factory:
        transcribe(wav)
        transcriber.reset_client()
        transcribe(wav)

    assert factory.call_count == 2


def test_returns_stripped_text(tmp_path):
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 36)

    mock_response = MagicMock()
    mock_response.text = "  hello world  "

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = mock_response

    with patch("voiceflow.transcriber.OpenAI", return_value=mock_client):
        result = transcribe(wav)

    assert result == "hello world"
    mock_client.audio.transcriptions.create.assert_called_once()
    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-4o-mini-transcribe"
    assert call_kwargs["timeout"] == 30


def test_raises_transcription_error_on_api_failure(tmp_path):
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 36)

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = RuntimeError("network error")

    with patch("voiceflow.transcriber.OpenAI", return_value=mock_client):
        with pytest.raises(TranscriptionError) as exc_info:
            transcribe(wav)

    assert "Transcription call failed" in str(exc_info.value)
    assert exc_info.value.__cause__ is not None
