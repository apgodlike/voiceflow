"""Tests for transcriber.py — monkeypatched OpenAI client."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from voiceflow.transcriber import TranscriptionError, transcribe


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
    assert call_kwargs["model"] == "whisper-1"
    assert call_kwargs["timeout"] == 30


def test_raises_transcription_error_on_api_failure(tmp_path):
    wav = tmp_path / "test.wav"
    wav.write_bytes(b"RIFF" + b"\x00" * 36)

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = RuntimeError("network error")

    with patch("voiceflow.transcriber.OpenAI", return_value=mock_client):
        with pytest.raises(TranscriptionError) as exc_info:
            transcribe(wav)

    assert "Whisper call failed" in str(exc_info.value)
    assert exc_info.value.__cause__ is not None
