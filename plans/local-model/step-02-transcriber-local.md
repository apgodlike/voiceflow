# Step 02 — Create voiceflow/transcriber_local.py

**Phase:** P2 (parallel with step-03)
**Depends on:** step-01 (branch must exist)

## Context

Working directory: `C:\dev\projects\voice-typing\voiceflow`
Branch: `feature/local-model`

This creates the local Whisper transcription backend. It mirrors the public interface
of `voiceflow/transcriber.py` (`transcribe()`, `TranscriptionError`) but uses
`faster-whisper` running locally on CPU.

Two locks:
- `_init_lock` — protects model load/swap (prevents double-init under concurrent first calls)
- `_infer_lock` — serializes CPU inference (prevents CPU thrash when segment pipeline
  submits multiple concurrent calls via ThreadPoolExecutor)

`beam_size=1` + `vad_filter=True` = fastest real-time settings.

## Task

Create a new file `C:\dev\projects\voice-typing\voiceflow\voiceflow\transcriber_local.py`
with exactly this content:

```python
"""Local Whisper transcription via faster-whisper — CPU-serialized for CPU-only systems."""
import argparse
import logging
import threading
import time
from pathlib import Path

logger = logging.getLogger("voiceflow.transcriber_local")

_init_lock = threading.Lock()
_infer_lock = threading.Lock()

_model_instance = None
_model_name_loaded: str | None = None

_MODEL_SIZES = {
    "tiny": "75 MB",
    "base": "145 MB",
    "small": "485 MB",
    "medium": "1.5 GB",
    "large": "3 GB",
}


class TranscriptionError(Exception):
    pass


def _load_model(model_name: str):
    global _model_instance, _model_name_loaded
    with _init_lock:
        if _model_instance is None or _model_name_loaded != model_name:
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                raise TranscriptionError(
                    "faster-whisper not installed — run: pip install faster-whisper"
                )
            size = _MODEL_SIZES.get(model_name, "?")
            logger.info(
                "Loading local Whisper model '%s' (~%s — downloading on first use)",
                model_name, size,
            )
            _model_instance = WhisperModel(model_name, device="cpu", compute_type="int8")
            _model_name_loaded = model_name
            logger.info("Model '%s' ready.", model_name)
    return _model_instance


def reset_model() -> None:
    """Drop the cached model to free RAM. Next transcribe() call reloads."""
    global _model_instance, _model_name_loaded
    with _init_lock:
        _model_instance = None
        _model_name_loaded = None


def is_loaded() -> bool:
    """Return True if a model is currently loaded in memory."""
    return _model_instance is not None


def transcribe(audio_path: Path, language: str | None = None, model_name: str = "base") -> str:
    """Transcribe audio_path using a local Whisper model.

    Serializes inference via _infer_lock so concurrent segment calls
    don't thrash the CPU. Raises TranscriptionError on any failure.
    """
    size_kb = audio_path.stat().st_size / 1024
    logger.info(
        "Transcribing %s (%.1f KB) via local whisper-%s", audio_path.name, size_kb, model_name
    )
    t0 = time.monotonic()
    try:
        model = _load_model(model_name)
        with _infer_lock:
            segments, _ = model.transcribe(
                str(audio_path),
                language=language or None,
                beam_size=1,
                vad_filter=True,
            )
            text = " ".join(seg.text for seg in segments).strip()
        elapsed = time.monotonic() - t0
        logger.info("Local transcription done in %.2fs (%d chars)", elapsed, len(text))
        return text
    except TranscriptionError:
        raise
    except Exception as exc:
        raise TranscriptionError(f"Local transcription failed: {exc}") from exc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoke-test local Whisper transcription")
    parser.add_argument("audio_path", type=Path)
    parser.add_argument("--model", default="base",
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--language", default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    print(transcribe(args.audio_path, language=args.language, model_name=args.model))
```

## Acceptance Criteria

- File exists at `voiceflow/transcriber_local.py`
- `python -c "from voiceflow.transcriber_local import transcribe, TranscriptionError, reset_model, is_loaded; print('OK')"` prints `OK`
