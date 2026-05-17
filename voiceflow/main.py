"""VoiceFlow entry point — wires all modules together."""
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

from voiceflow import cleaner, paster, queue as q, recorder, transcriber
from voiceflow.hotkey import HotkeyController
from voiceflow.tray import Tray
from voiceflow.transcriber import TranscriptionError

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("voiceflow.main")

_shutdown = threading.Event()
_current_rid: str | None = None
_tray: Tray | None = None
_queue_module = q
_executor: ThreadPoolExecutor | None = None


def _process_job(rid: str, audio_path: Path) -> None:
    assert _tray is not None
    _tray.set_state("transcribing")
    try:
        raw = transcriber.transcribe(audio_path)
        cleaned = cleaner.clean(raw)
        paster.paste(cleaned)
        _queue_module.mark_success(rid, raw, cleaned)
        _tray.notify("VoiceFlow", f"Pasted: {cleaned[:60]}")
    except TranscriptionError as exc:
        _queue_module.mark_failed(rid, str(exc))
        _tray.notify("VoiceFlow failed", str(exc))
        logger.error("Transcription failed for %s: %s", rid, exc)
    finally:
        _tray.set_state("idle")
        _tray.set_failed_count(len(_queue_module.list_pending()))


def _on_start() -> None:
    global _current_rid
    _current_rid = recorder.start_recording()
    logger.info("Recording started: %s", _current_rid)
    if _tray:
        _tray.set_state("recording")


def _on_stop() -> None:
    global _current_rid
    rid = _current_rid
    if rid is None:
        return
    _current_rid = None
    audio = recorder.stop_recording(rid)
    logger.info("Recording stopped: %s → %s", rid, audio)
    _queue_module.enqueue(rid, audio)
    if _executor:
        _executor.submit(_process_job, rid, audio)
    if _tray:
        _tray.set_state("idle")


def _sweeper() -> None:
    while not _shutdown.is_set():
        pending = list(_queue_module.retry_all())
        for job in pending:
            if _shutdown.is_set():
                break
            logger.info("Sweeper retrying: %s (attempt %d)", job.recording_id, job.attempts + 1)
            audio = Path(job.wav_path)
            if audio.exists() and _executor:
                _executor.submit(_process_job, job.recording_id, audio)
        _shutdown.wait(60)


def main() -> None:
    global _tray, _executor

    _tray = Tray(on_quit=_shutdown.set)
    _executor = ThreadPoolExecutor(max_workers=2)

    pending = list(_queue_module.retry_all())
    for job in pending:
        audio = Path(job.wav_path)
        if audio.exists():
            logger.info("Startup sweep: retrying %s", job.recording_id)
            _executor.submit(_process_job, job.recording_id, audio)

    sweeper = threading.Thread(target=_sweeper, daemon=True, name="sweeper")
    sweeper.start()

    hotkey = HotkeyController(on_start=_on_start, on_stop=_on_stop)
    hotkey.start()
    logger.info("VoiceFlow ready. Hold Ctrl+Alt to record, or double-tap to toggle.")

    # run_detached() puts pystray's Win32 message pump on a daemon thread,
    # freeing the main thread to run Python code that responds to Ctrl+C.
    _tray.run_detached()
    try:
        while not _shutdown.is_set():
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        _shutdown.set()
        _tray.stop()
        hotkey.stop()
        _executor.shutdown(wait=False)
        logger.info("VoiceFlow shut down.")
        os._exit(0)  # ThreadPoolExecutor threads are non-daemon; force exit


if __name__ == "__main__":
    main()
