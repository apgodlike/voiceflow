"""VoiceFlow entry point — wires all modules together via the App orchestrator."""
import logging
import logging.handlers
import os
import signal
import threading
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

from voiceflow import cleaner, config, paster, paths, queue as q, recorder, startup, transcriber
from voiceflow.hotkey import HotkeyController
from voiceflow.tray import Tray
from voiceflow.transcriber import TranscriptionError
from voiceflow.ui import UI

logger = logging.getLogger("voiceflow.main")

SWEEP_INTERVAL_SEC = 60
MAX_WORKERS = 4  # segments transcribe concurrently during recording
SEGMENT_RESULT_TIMEOUT_SEC = 60
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
        self._max_timer: threading.Timer | None = None
        self._cfg = config.load()
        self._apply_config_env()
        self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)
        # Per-recording segment fast-path state (one recording active at a time).
        self._seg_lock = threading.Lock()
        self._stop_lock = threading.Lock()
        self._seg_futures: dict[int, Future] = {}
        self._seg_paths: dict[int, Path] = {}
        self._recent_texts: deque[str] = deque(maxlen=5)
        # Fresh install = config file doesn't exist yet → show wizard.
        # Returning user = config exists → start hidden in tray.
        self._is_first_run = not paths.CONFIG_PATH.exists()
        _has_key = (
            bool(self._cfg.get("openai_api_key", ""))
            or self._cfg.get("backend") == "local"
        )
        # Force window visible on first run regardless of env-level API key.
        _start_hidden = _has_key and not self._is_first_run
        self._ui = UI(
            self._cfg,
            on_settings_saved=self._on_settings_saved,
            on_startup_toggle=self._on_startup_toggle,
            start_hidden=_start_hidden,
        )
        self._tray = Tray(
            on_quit=self._quit,
            on_retry=self._trigger_retry,
            on_open=self._ui.show_window,
            on_settings=self._ui.open_settings,
            on_paste_previous=self._paste_previous,
            on_backend_toggle=self._toggle_backend,
        )
        self._tray.set_backend(self._cfg.get("backend", "openai"))
        self._hotkey = HotkeyController(on_start=self._on_start, on_stop=self._on_stop)

    # ── config ────────────────────────────────────────────────────────────────

    def _apply_config_env(self) -> None:
        """Push resolved key/model into the env so transcriber stays decoupled."""
        key = config.resolved_api_key(self._cfg)
        if key:
            os.environ["OPENAI_API_KEY"] = key
        os.environ["VOICEFLOW_MODEL"] = config.resolved_model(self._cfg)
        transcriber.reset_client()  # key/model may have changed — rebuild lazily
        if self._cfg.get("backend", "openai") == "openai":
            try:
                from voiceflow import transcriber_local
                transcriber_local.reset_model()
            except ImportError:
                pass

    def _transcribe(self, audio_path: Path, language: str | None = None) -> str:
        """Dispatch transcription to openai or local backend per config."""
        backend = self._cfg.get("backend", "openai")
        if backend == "local":
            from voiceflow import transcriber_local
            model_name = self._cfg.get("local_model", "distil-small.en")
            if not transcriber_local.is_loaded():
                self._ui.toast(f"Loading local Whisper model '{model_name}'…")
            return transcriber_local.transcribe(audio_path, language=language,
                                                model_name=model_name)
        return transcriber.transcribe(audio_path, language=language)

    def _on_setup_complete(self, cfg: dict) -> None:
        """Called by the setup wizard when the user finishes first-run setup."""
        self._cfg.update(cfg)
        config.save(self._cfg)
        self._apply_config_env()
        startup.apply(self._cfg.get("start_on_login", True))
        self._tray.set_backend(self._cfg.get("backend", "openai"))
        self._ui.hide()
        self._ui.toast("VoiceFlow ready! Hold Ctrl+Alt to start recording.")

    def _preload_local_model(self) -> None:
        """Load the configured local model into RAM in the background on startup."""
        model_name = self._cfg.get("local_model", "distil-small.en")

        def _load() -> None:
            try:
                from voiceflow import transcriber_local
                if not transcriber_local.is_loaded():
                    logger.info("Preloading local model '%s'…", model_name)
                    transcriber_local._load_model(model_name)
                    logger.info("Local model '%s' ready.", model_name)
            except Exception as exc:
                logger.warning("Local model preload failed: %s", exc)

        threading.Thread(target=_load, daemon=True, name="model-preload").start()

    def _on_settings_saved(self, cfg: dict) -> None:
        config.save(cfg)
        self._apply_config_env()
        startup.apply(cfg.get("start_on_login", True))
        if cfg.get("backend") == "local":
            self._preload_local_model()

    def _on_startup_toggle(self, enabled: bool) -> None:
        self._cfg["start_on_login"] = enabled
        config.save(self._cfg)
        startup.apply(enabled)

    def _toggle_backend(self) -> None:
        current = self._cfg.get("backend", "openai")
        new_backend = "local" if current == "openai" else "openai"
        self._cfg["backend"] = new_backend
        config.save(self._cfg)
        self._apply_config_env()
        self._tray.set_backend(new_backend)
        if new_backend == "local":
            model = self._cfg.get("local_model", "distil-small.en")
            self._ui.toast(f"Backend → local ({model})")
        else:
            self._ui.toast("Backend → openai")

    def _set_state(self, state: str) -> None:
        self._tray.set_state(state)
        self._ui.set_state(state)

    # ── pipeline ────────────────────────────────────────────────────────────

    def _process_job(self, rid: str, audio_path: Path) -> None:
        """Full-file path: single transcription of the whole recording.

        Used by the retry sweeper and as the fast-path fallback. Owns the
        queue success/failure transitions for ``rid``.
        """
        self._set_state("transcribing")
        try:
            raw = self._transcribe(audio_path, language=self._cfg.get("language") or None)
            cleaned = self._clean(raw)
            paster.paste(
                cleaned,
                preserve_clipboard=self._cfg.get("preserve_clipboard", False),
                paste_mode=self._cfg.get("paste_mode", "clipboard"),
            )
            q.mark_success(rid)
            self._on_paste_success(cleaned)
        except TranscriptionError as exc:
            q.mark_failed(rid, str(exc))
            self._ui.toast("Transcription failed — will retry")
            logger.error("Transcription failed for %s: %s", rid, exc)
        finally:
            self._set_state("idle")
            self._tray.set_failed_count(len(q.list_pending()))

    def _clean(self, raw: str) -> str:
        """Apply the cleaner with the user's current config-driven options."""
        return cleaner.clean(
            raw,
            dictionary=self._cfg.get("dictionary"),
            extra_fillers=self._cfg.get("extra_fillers"),
            voice_commands=self._cfg.get("voice_commands", False),
            code_mode=self._cfg.get("code_mode", False),
            raw_mode=self._cfg.get("raw_mode", False),
        )

    def _on_paste_success(self, cleaned: str) -> None:
        self._recent_texts.appendleft(cleaned)
        self._tray.set_has_previous(True)
        self._ui.toast("Pasted ✓")

    def _on_rms_update(self, rms: float) -> None:
        """Called from the audio thread — just forwards to UI (no Tk calls here)."""
        self._ui.update_rms(rms)

    def _paste_previous(self) -> None:
        if not self._recent_texts:
            return
        paster.paste(
            self._recent_texts[0],
            preserve_clipboard=self._cfg.get("preserve_clipboard", False),
            paste_mode=self._cfg.get("paste_mode", "clipboard"),
        )
        self._ui.toast("Pasted previous ✓")

    # Segments smaller than this are too short for the OpenAI API (~0.3 s of
    # 16 kHz OGG). Sending them returns 400 "Audio file might be corrupted".
    _MIN_SEGMENT_BYTES = 8_000

    def _on_segment(self, index: int, path: Path) -> None:
        """A segment closed mid-recording — start transcribing it now.

        Only the OpenAI backend uses the per-segment fast-path: those calls are
        network-bound and parallelize, so transcribing during recording cuts
        latency. The local Whisper backend does the opposite — its encoder runs
        a full 30 s window per call, so each short segment re-pays that fixed
        cost. Local therefore transcribes the whole file once on stop (see
        ``_finalize_local``); here we only track the segment path for cleanup.
        """
        try:
            if path.stat().st_size < self._MIN_SEGMENT_BYTES:
                path.unlink(missing_ok=True)
                return
        except OSError:
            return
        if self._cfg.get("backend") == "local":
            with self._seg_lock:
                self._seg_paths[index] = path
            return
        lang = self._cfg.get("language") or None
        fut = self._executor.submit(self._transcribe, path, lang)
        with self._seg_lock:
            self._seg_futures[index] = fut
            self._seg_paths[index] = path

    def _finalize_job(self, rid: str, full_path: Path, futures: dict[int, Future],
                      seg_paths: dict[int, Path]) -> None:
        """Stitch the per-segment transcriptions in order and paste.

        On any segment error, discard the partial result and fall back to a
        single transcription of the full file (which keeps the queue/retry
        and privacy model intact). Segment temp files are always deleted.
        """
        self._set_state("transcribing")
        try:
            if not futures:
                # No segments collected (e.g. backend toggled mid-recording) —
                # transcribe the whole file rather than dropping the recording.
                self._process_job(rid, full_path)
                return
            try:
                parts = [
                    (futures[i].result(timeout=SEGMENT_RESULT_TIMEOUT_SEC) or "")
                    for i in sorted(futures)
                ]
            except Exception as exc:
                logger.warning("Segment fast-path failed for %s, using full file: %s", rid, exc)
                self._process_job(rid, full_path)
                return
            raw = " ".join(p for p in parts if p).strip()
            if not raw:
                q.mark_success(rid)  # nothing said — drop the recording
                return
            cleaned = self._clean(raw)
            paster.paste(
                cleaned,
                preserve_clipboard=self._cfg.get("preserve_clipboard", False),
                paste_mode=self._cfg.get("paste_mode", "clipboard"),
            )
            q.mark_success(rid)
            self._on_paste_success(cleaned)
        finally:
            self._cleanup_segments(seg_paths)
            self._set_state("idle")
            self._tray.set_failed_count(len(q.list_pending()))

    def _finalize_local(self, rid: str, full_path: Path,
                        seg_paths: dict[int, Path]) -> None:
        """Local backend: one transcription of the whole file (no segment
        stitching). Avoids the per-segment 30 s encoder tax and yields a single
        coherent transcript (no false sentence breaks at pauses)."""
        try:
            self._process_job(rid, full_path)
        finally:
            self._cleanup_segments(seg_paths)

    @staticmethod
    def _cleanup_segments(seg_paths: dict[int, Path]) -> None:
        for p in seg_paths.values():
            Path(p).unlink(missing_ok=True)

    def _start_max_timer(self) -> None:
        self._cancel_max_timer()
        secs = self._cfg.get("max_recording_sec", 600)
        if secs and secs > 0:
            self._max_timer = threading.Timer(secs, self._auto_stop)
            self._max_timer.daemon = True
            self._max_timer.start()

    def _cancel_max_timer(self) -> None:
        if self._max_timer is not None:
            self._max_timer.cancel()
            self._max_timer = None

    def _auto_stop(self) -> None:
        """Fired by the duration timer — stop a runaway recording and tell the
        user so they can start a fresh one."""
        if self._current_rid is None:
            return
        secs = self._cfg.get("max_recording_sec", 600)
        logger.info("Max recording duration (%ss) reached — auto-stopping", secs)
        self._ui.toast(f"Recording stopped — {secs // 60} min limit. Start again to continue.")
        self._on_stop()

    def _on_start(self) -> None:
        with self._seg_lock:
            self._seg_futures = {}
            self._seg_paths = {}
        self._current_rid = recorder.start_recording(
            on_segment=self._on_segment,
            device=self._cfg.get("input_device"),
            on_rms=self._on_rms_update,
        )
        logger.info("Recording started: %s", self._current_rid)
        self._set_state("recording")
        self._start_max_timer()

    def _on_stop(self) -> None:
        with self._stop_lock:
            rid = self._current_rid
            if rid is None:
                return
            self._cancel_max_timer()
            self._current_rid = None
        full = recorder.stop_recording(rid)  # fires on_segment for the final segment
        logger.info("Recording stopped: %s", rid)
        with self._seg_lock:
            futures = dict(self._seg_futures)
            seg_paths = dict(self._seg_paths)
        q.enqueue(rid, full)  # durable fallback unit
        self._set_state("transcribing")
        if self._cfg.get("backend") == "local":
            target, args = self._finalize_local, (rid, full, seg_paths)
        else:
            target, args = self._finalize_job, (rid, full, futures, seg_paths)
        threading.Thread(
            target=target, args=args,
            daemon=True, name=f"finalize-{rid[:8]}",
        ).start()

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

    def _adopt_orphaned_jobs(self) -> None:
        """Pending jobs left from a previous crash were never attempted.
        Mark them failed so retry_all() picks them up for retry."""
        for job in q.list_pending():
            if job.status == "pending":
                logger.info("Adopting orphaned job %s", job.recording_id)
                q.mark_failed(job.recording_id, "orphaned from previous session")

    def run(self) -> None:
        self._adopt_orphaned_jobs()
        self._sweep_once()  # retry anything left over from a previous run
        threading.Thread(target=self._sweeper, daemon=True, name="sweeper").start()
        self._hotkey.start()
        # pystray on a detached daemon thread; Tk owns the main thread below.
        self._tray.run_detached()
        if self._is_first_run:
            logger.info("First run — showing setup wizard.")
            self._ui.open_setup_wizard(on_complete=self._on_setup_complete)
        elif self._cfg.get("backend") == "local":
            self._preload_local_model()
        elif not config.resolved_api_key(self._cfg):
            logger.info("No API key configured — showing settings.")
            self._ui.open_settings()
        logger.info("VoiceFlow ready. Hold Ctrl+Alt to record, or double-tap to toggle.")

        self._ui.run()  # blocks on the Tk mainloop until the window is destroyed
        self.shutdown()

    def _quit(self) -> None:
        """Triggered from the tray Quit item — end the Tk mainloop."""
        self._shutdown.set()
        self._ui.stop()

    def shutdown(self) -> None:
        self._shutdown.set()
        self._cancel_max_timer()
        self._tray.stop()
        self._hotkey.stop()
        self._executor.shutdown(wait=False, cancel_futures=True)
        logger.info("VoiceFlow shut down.")


def main() -> None:
    load_dotenv()
    _setup_logging()
    # Tkinter's mainloop runs in C and doesn't check Python signals; install a
    # handler so Ctrl+C in the terminal kills the process immediately.
    signal.signal(signal.SIGINT, lambda *_: os._exit(130))
    App().run()
    os._exit(0)  # tray/pool threads can linger; guarantee process death


if __name__ == "__main__":
    main()
