"""VoiceFlow entry point — wires all modules together via the App orchestrator."""
import logging
import logging.handlers
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

from voiceflow import cleaner, paster, paths, queue as q, recorder, transcriber
from voiceflow.hotkey import HotkeyController
from voiceflow.tray import Tray
from voiceflow.transcriber import TranscriptionError

logger = logging.getLogger("voiceflow.main")

SWEEP_INTERVAL_SEC = 60
MAX_WORKERS = 2
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def _setup_logging() -> None:
    """File log in the data dir (no console when frozen/windowed).

    Dictated transcripts are never logged — only metadata (timing, counts,
    filenames). See the privacy design in queue.py / transcriber.py.
    """
    paths.BASE_DIR.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter(_LOG_FORMAT)
    file_handler = logging.handlers.RotatingFileHandler(
        paths.LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console)


class App:
    """Owns the runtime: tray, hotkey, worker pool, retry sweeper, lifecycle.

    Replaces module-level globals so state is encapsulated and testable.
    """

    def __init__(self) -> None:
        self._shutdown = threading.Event()
        self._current_rid: str | None = None
        self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        self._tray = Tray(on_quit=self._shutdown.set, on_retry=self._trigger_retry)
        self._hotkey = HotkeyController(on_start=self._on_start, on_stop=self._on_stop)

    # ── pipeline ────────────────────────────────────────────────────────────

    def _process_job(self, rid: str, audio_path: Path) -> None:
        self._tray.set_state("transcribing")
        try:
            raw = transcriber.transcribe(audio_path)
            cleaned = cleaner.clean(raw)
            paster.paste(cleaned)
            q.mark_success(rid)
            self._tray.notify("VoiceFlow", "Pasted")
        except TranscriptionError as exc:
            q.mark_failed(rid, str(exc))
            self._tray.notify("VoiceFlow", "Transcription failed — will retry")
            logger.error("Transcription failed for %s: %s", rid, exc)
        finally:
            self._tray.set_state("idle")
            self._tray.set_failed_count(len(q.list_pending()))

    def _on_start(self) -> None:
        self._current_rid = recorder.start_recording()
        logger.info("Recording started: %s", self._current_rid)
        self._tray.set_state("recording")

    def _on_stop(self) -> None:
        rid = self._current_rid
        if rid is None:
            return
        self._current_rid = None
        audio = recorder.stop_recording(rid)
        logger.info("Recording stopped: %s", rid)
        q.enqueue(rid, audio)
        self._executor.submit(self._process_job, rid, audio)
        self._tray.set_state("idle")

    # ── retry sweeper ─────────────────────────────────────────────────────────

    def _sweep_once(self) -> None:
        for job in q.retry_all():
            if self._shutdown.is_set():
                break
            audio = Path(job.audio_path)
            if audio.exists():
                logger.info("Retrying %s (attempt %d)", job.recording_id, job.attempts + 1)
                self._executor.submit(self._process_job, job.recording_id, audio)

    def _sweeper(self) -> None:
        while not self._shutdown.is_set():
            self._sweep_once()
            self._shutdown.wait(SWEEP_INTERVAL_SEC)

    def _trigger_retry(self) -> None:
        """Immediate retry from the tray menu, off the UI thread."""
        threading.Thread(target=self._sweep_once, daemon=True).start()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        self._sweep_once()  # retry anything left over from a previous run
        threading.Thread(target=self._sweeper, daemon=True, name="sweeper").start()
        self._hotkey.start()
        logger.info("VoiceFlow ready. Hold Ctrl+Alt to record, or double-tap to toggle.")

        # run_detached() puts pystray's Win32 message pump on a daemon thread,
        # freeing the main thread to run Python code that responds to Ctrl+C.
        self._tray.run_detached()
        try:
            while not self._shutdown.is_set():
                time.sleep(0.2)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        self._shutdown.set()
        self._tray.stop()
        self._hotkey.stop()
        self._executor.shutdown(wait=False, cancel_futures=True)
        logger.info("VoiceFlow shut down.")


def main() -> None:
    load_dotenv()
    _setup_logging()
    App().run()
    os._exit(0)  # tray/pool threads can linger; guarantee process death


if __name__ == "__main__":
    main()
