"""Local transcription via NVIDIA Parakeet-TDT-0.6B (ONNX, CPU).

A second local engine alongside ``transcriber_local`` (faster-whisper). Parakeet
has no fixed encoder window, so latency scales linearly with audio length with no
per-call floor — a 30 s clip transcribes in ~2 s on a multi-core CPU, and it stays
silent on silence/noise instead of hallucinating. English-only.

Runs the int8-quantized model via ``onnx-asr`` + ``onnxruntime`` (~660 MB download,
~760 MB RAM). Same ``transcribe(audio_path, language)`` contract as the other
backends; ``language`` is ignored (English).

Model weights: NVIDIA Parakeet-TDT-0.6B-v2, license CC-BY-4.0 (see NOTICE).
"""
import argparse
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger("voiceflow.transcriber_parakeet")

MODEL_ID = "nemo-parakeet-tdt-0.6b-v2"
QUANTIZATION = "int8"
_TARGET_SR = 16000

_init_lock = threading.Lock()
_infer_lock = threading.Lock()
_model_instance = None


class TranscriptionError(Exception):
    pass


def _cpu_threads() -> int:
    """Physical cores, not logical — matches transcriber_local's reasoning."""
    logical = os.cpu_count() or 4
    return max(1, logical // 2) if logical >= 8 else logical


def _load_model():
    global _model_instance
    with _init_lock:
        if _model_instance is None:
            try:
                import onnx_asr
                import onnxruntime as ort
            except ImportError as exc:
                raise TranscriptionError(
                    "onnx-asr / onnxruntime not installed — run: pip install onnx-asr onnxruntime"
                ) from exc
            so = ort.SessionOptions()
            so.intra_op_num_threads = _cpu_threads()
            so.inter_op_num_threads = 1
            logger.info("Loading Parakeet (%s, %s, %d threads)…",
                        MODEL_ID, QUANTIZATION, so.intra_op_num_threads)
            _model_instance = onnx_asr.load_model(
                MODEL_ID, quantization=QUANTIZATION, sess_options=so,
                providers=["CPUExecutionProvider"],
            )
            logger.info("Parakeet ready.")
    return _model_instance


def reset_model() -> None:
    """Drop the cached model to free RAM. Next transcribe() reloads."""
    global _model_instance
    with _init_lock:
        _model_instance = None


def is_loaded() -> bool:
    return _model_instance is not None


def _read_audio(audio_path: Path):
    import soundfile as sf
    audio, sr = sf.read(str(audio_path), dtype="float32")
    if audio.ndim > 1:
        audio = audio[:, 0]
    return audio, sr


def transcribe(audio_path: Path, language: str | None = None, model_name: str = "parakeet") -> str:
    """Transcribe ``audio_path`` with Parakeet. ``language``/``model_name`` are
    accepted for signature parity with the other backends and ignored."""
    size_kb = audio_path.stat().st_size / 1024
    logger.info("Transcribing %s (%.1f KB) via Parakeet", audio_path.name, size_kb)
    t0 = time.monotonic()
    try:
        model = _load_model()
        audio, sr = _read_audio(audio_path)
        with _infer_lock:
            text = (model.recognize(audio, sample_rate=sr) or "").strip()
        logger.info("Parakeet transcription done in %.2fs (%d chars)",
                    time.monotonic() - t0, len(text))
        return text
    except TranscriptionError:
        raise
    except Exception as exc:
        raise TranscriptionError(f"Parakeet transcription failed: {exc}") from exc


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smoke-test Parakeet transcription")
    parser.add_argument("audio_path", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    print(transcribe(args.audio_path))
