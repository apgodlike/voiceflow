"""Local Whisper transcription via faster-whisper — CPU-serialized for CPU-only systems."""
import argparse
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger("voiceflow.transcriber_local")


def _cpu_threads() -> int:
    """Threads for CTranslate2 inference — physical cores, not logical.

    CTranslate2's auto setting over-subscribes hyper-threaded CPUs (e.g. uses
    12 threads on a 6-core/12-thread chip), which measured ~15% slower than
    pinning to the 6 physical cores. We can't detect hyper-threading from the
    stdlib, so assume HT on 8+ logical cores and halve; otherwise use all.
    """
    logical = os.cpu_count() or 4
    return max(1, logical // 2) if logical >= 8 else logical

_init_lock = threading.Lock()
_infer_lock = threading.Lock()

_model_instance = None
_model_name_loaded: str | None = None

_MODEL_SIZES = {
    "tiny": "75 MB", "tiny.en": "75 MB",
    "base": "145 MB", "base.en": "145 MB",
    "small": "485 MB", "small.en": "485 MB", "distil-small.en": "330 MB",
    "medium": "1.5 GB", "medium.en": "1.5 GB", "distil-medium.en": "790 MB",
    "large": "3 GB", "distil-large-v3": "1.5 GB",
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
            threads = _cpu_threads()
            logger.info(
                "Loading local Whisper model '%s' (~%s — downloading on first use, %d threads)",
                model_name, size, threads,
            )
            _model_instance = WhisperModel(
                model_name, device="cpu", compute_type="int8", cpu_threads=threads
            )
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
                # Each dictation segment is independent; not feeding prior text
                # avoids a slow per-window dependency and stops the model from
                # looping/hallucinating on silence. Faster + safer on CPU.
                condition_on_previous_text=False,
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
