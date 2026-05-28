"""OpenAI transcription — single call, no retry logic (queue.py owns retries)."""
import argparse
import logging
import os
import time
from pathlib import Path

from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

logger = logging.getLogger("voiceflow.transcriber")

_client: OpenAI | None = None


class TranscriptionError(Exception):
    pass


def _get_client() -> OpenAI:
    """Reused across calls so the HTTP connection pool / TLS session persists.

    A fresh OpenAI() per call re-did the TLS handshake every time; caching it
    removes that setup cost from each transcription.
    """
    global _client
    if _client is None:
        _client = OpenAI()
    return _client


def reset_client() -> None:
    """Drop the cached client so the next call rebuilds it (e.g. after the
    API key changes in Settings — the client reads the key at construction)."""
    global _client
    _client = None


def _model() -> str:
    return os.environ.get("VOICEFLOW_MODEL", "gpt-4o-mini-transcribe")


def transcribe(audio_path: Path, language: str | None = None) -> str:
    client = _get_client()
    size_kb = audio_path.stat().st_size / 1024
    model = _model()
    logger.info("Transcribing %s (%.1f KB) via %s", audio_path.name, size_kb, model)
    t0 = time.monotonic()
    try:
        extra: dict = {"language": language} if language else {}
        with open(audio_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model=model,
                file=f,
                timeout=30,
                **extra,
            )
        elapsed = time.monotonic() - t0
        logger.info("Transcription done in %.2fs (%d chars)", elapsed, len(response.text))
        return response.text.strip()
    except AuthenticationError as exc:
        raise TranscriptionError(f"Auth failed — check OPENAI_API_KEY: {exc}") from exc
    except RateLimitError as exc:
        raise TranscriptionError(f"Rate limited — retry later: {exc}") from exc
    except APITimeoutError as exc:
        raise TranscriptionError(f"Timed out after 30s: {exc}") from exc
    except APIConnectionError as exc:
        raise TranscriptionError(f"Network error: {exc}") from exc
    except Exception as exc:
        raise TranscriptionError(f"Transcription call failed: {exc}") from exc


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("audio_path", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    print(transcribe(args.audio_path))
