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


class TranscriptionError(Exception):
    pass


def _model() -> str:
    return os.environ.get("VOICEFLOW_MODEL", "gpt-4o-mini-transcribe")


def transcribe(audio_path: Path) -> str:
    client = OpenAI()
    size_kb = audio_path.stat().st_size / 1024
    model = _model()
    logger.info("Transcribing %s (%.1f KB) via %s", audio_path.name, size_kb, model)
    t0 = time.monotonic()
    try:
        with open(audio_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model=model,
                file=f,
                timeout=30,
            )
        elapsed = time.monotonic() - t0
        logger.info("Transcription done in %.2fs: %r", elapsed, response.text[:80])
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
