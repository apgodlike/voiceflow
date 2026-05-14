"""OpenAI Whisper transcription — single call, no retry logic (queue.py owns retries)."""
import argparse
import sys
from pathlib import Path

from openai import OpenAI


class TranscriptionError(Exception):
    pass


def transcribe(wav_path: Path) -> str:
    client = OpenAI()
    try:
        with open(wav_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                timeout=30,
            )
        return response.text.strip()
    except Exception as exc:
        raise TranscriptionError(f"Whisper call failed: {exc}") from exc


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("wav_path", type=Path)
    args = parser.parse_args()
    print(transcribe(args.wav_path))
