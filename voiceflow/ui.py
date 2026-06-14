"""Tkinter UI: main window, recording overlay, silent toast, settings dialog.

All widgets share one ``Tk`` root that MUST own the main thread (Tk is not
thread-safe). Worker threads call the public methods, which marshal onto the Tk
thread via ``root.after``. pystray runs on its own detached thread, so the two
event loops do not fight.

No method here makes a sound — toasts are silent by design.
"""
import json
import logging
import math
import os
import time as _time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from voiceflow import paths

logger = logging.getLogger("voiceflow.ui")

_COLORS = {"recording": "#e03030", "transcribing": "#e0a000", "idle": "#808080"}
_MODELS = ["gpt-4o-mini-transcribe", "gpt-4o-transcribe"]
_SYSTEM_DEFAULT_DEV = "System default"
_LOCAL_MODEL_SIZES = [
    "tiny", "tiny.en", "base", "base.en", "small", "small.en",
    "distil-small.en", "medium", "medium.en", "distil-medium.en",
    "large", "distil-large-v3",
]

# ── animated overlay geometry ──────────────────────────────────────────────────
_OV_TRANSPARENT = "#000001"   # Windows transparentcolor sentinel — these pixels vanish
_OV_PILL = "#1c1c1e"          # pill fill (dark, near-black)

_BAR_COUNT = 9                # odd number → clean center bar
_BAR_W = 3
_BAR_GAP = 4
_BARS_W = _BAR_COUNT * _BAR_W + (_BAR_COUNT - 1) * _BAR_GAP  # 27+32 = 59 px
_OVERLAY_H = 44
_OVERLAY_W = 110              # wide enough for pill proportions
_PAD_X = (_OVERLAY_W - _BARS_W) // 2                          # center bars in pill
_BAR_MAX_H = 28               # center bar max height
_BAR_MIN_H = 3
_ANIM_MS = 40                 # 25 fps



def _draw_pill_bg(canvas: tk.Canvas, w: int, h: int, fill: str) -> None:
    """Paint a fully-rounded capsule covering (0,0)→(w,h) on canvas."""
    r = h // 2
    canvas.create_oval(0, 0, 2 * r, h, fill=fill, outline="")
    canvas.create_oval(w - 2 * r, 0, w, h, fill=fill, outline="")
    canvas.create_rectangle(r, 0, w - r, h, fill=fill, outline="")


def _query_input_devices() -> list[tuple[int, str]]:
    """Return [(index, display_name), ...] for input-capable devices.

    Index -1 is the sentinel for system default (maps to None in config).
    Returns only [(-1, "System default")] when sounddevice is unavailable.
    """
    result: list[tuple[int, str]] = [(-1, _SYSTEM_DEFAULT_DEV)]
    try:
        import sounddevice as sd  # optional — ui still works without mic hardware
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                result.append((i, dev["name"]))
    except Exception:
        pass
    return result

_HOWTO = (
    "Hold  Ctrl + Alt   → record while held, release to paste\n"
    "Double-tap Ctrl+Alt → toggle recording on/off\n\n"
    "Closing or minimizing this window keeps VoiceFlow running in the tray.\n"
    "Quit fully from the tray icon (right-click → Quit)."
)


class UI:
    def __init__(
        self,
        cfg: dict[str, Any],
        on_settings_saved: Callable[[dict[str, Any]], None],
        on_startup_toggle: Callable[[bool], None],
        start_hidden: bool = False,
    ) -> None:
        self._cfg = cfg
        self._on_settings_saved = on_settings_saved
        self._on_startup_toggle = on_startup_toggle

        self.root = tk.Tk()
        if start_hidden:
            self.root.withdraw()  # before any widgets — prevents the 1-frame flash
        self.root.title("VoiceFlow")
        self.root.geometry("420x300")
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)  # close → tray, not quit
        try:
            self.root.iconbitmap(str(paths.asset_path("icon.ico")))
        except tk.TclError:
            logger.debug("Window icon not set (icon.ico missing)")

        self._overlay: tk.Toplevel | None = None
        self._canvas: tk.Canvas | None = None
        self._overlay_state: str = "idle"
        self._anim_running: bool = False
        self._latest_rms: float = 0.0
        self._bar_heights: list[float] = [float(_BAR_MIN_H)] * _BAR_COUNT

        self._toast: tk.Toplevel | None = None
        self._build_main()

    # ── main window ───────────────────────────────────────────────────────────

    def _build_main(self) -> None:
        pad = {"padx": 16, "pady": 6}
        ttk.Label(self.root, text="VoiceFlow", font=("Segoe UI", 16, "bold")).pack(anchor="w", **pad)

        self._status = ttk.Label(self.root, text="● Running — ready", foreground="#2a8a2a")
        self._status.pack(anchor="w", padx=16)

        ttk.Separator(self.root).pack(fill="x", padx=16, pady=8)
        ttk.Label(self.root, text=_HOWTO, justify="left").pack(anchor="w", padx=16)

        self._startup_var = tk.BooleanVar(value=bool(self._cfg.get("start_on_login", True)))
        ttk.Checkbutton(
            self.root,
            text="Start VoiceFlow when I log in",
            variable=self._startup_var,
            command=lambda: self._on_startup_toggle(self._startup_var.get()),
        ).pack(anchor="w", padx=16, pady=(12, 4))

        ttk.Button(self.root, text="Settings…", command=self._open_settings).pack(anchor="w", padx=16, pady=8)

    def set_status(self, text: str, color: str = "#2a8a2a") -> None:
        self.root.after(0, lambda: self._status.config(text=text, foreground=color))

    # ── recording overlay — animated waveform ────────────────────────────────

    def set_state(self, state: str) -> None:
        self.root.after(0, self._apply_state, state)

    def update_rms(self, rms: float) -> None:
        """Called from the audio thread — assigns only, no Tk calls."""
        self._latest_rms = rms

    def _apply_state(self, state: str) -> None:
        self._overlay_state = state
        if state in ("recording", "transcribing"):
            self._overlay_show(state)
        else:
            self._latest_rms = 0.0
            self._overlay_hide()

    def _overlay_show(self, state: str) -> None:
        if self._overlay is None:
            self._overlay = tk.Toplevel(self.root)
            self._overlay.overrideredirect(True)
            self._overlay.attributes("-topmost", True)
            self._overlay.configure(bg=_OV_TRANSPARENT)
            # Make transparent key pixels invisible (rounded pill corners vanish)
            try:
                self._overlay.attributes("-transparentcolor", _OV_TRANSPARENT)
            except tk.TclError:
                pass  # non-Windows fallback — still works, just square corners
            self._canvas = tk.Canvas(
                self._overlay, width=_OVERLAY_W, height=_OVERLAY_H,
                bg=_OV_TRANSPARENT, highlightthickness=0,
            )
            self._canvas.pack()
            # Pill background is permanent — drawn once, never cleared
            _draw_pill_bg(self._canvas, _OVERLAY_W, _OVERLAY_H, _OV_PILL)
        self._overlay.deiconify()
        self._position(self._overlay, y_from_bottom=80)
        if not self._anim_running:
            self._anim_running = True
            self._animate_tick()

    def _overlay_hide(self) -> None:
        self._anim_running = False
        if self._overlay is not None:
            self._overlay.withdraw()

    def _animate_tick(self) -> None:
        if not self._anim_running or self._canvas is None:
            return
        if self._overlay_state == "recording":
            self._draw_recording_frame()
        else:
            self._draw_transcribing_frame()
        self._overlay.after(_ANIM_MS, self._animate_tick)  # type: ignore[union-attr]

    def _draw_recording_frame(self) -> None:
        """Bell-curve waveform: center bars tallest, outer bars shorter.

        Each bar's max amplitude is scaled by a Gaussian envelope centred on
        the middle bar. The voice component adds energy on top; idle keeps a
        low breathing motion even in silence so the indicator looks alive.
        """
        rms = self._latest_rms
        normalized = min(max(rms - 300, 0.0) / 4000.0, 1.0)
        t = _time.monotonic()
        canvas = self._canvas
        assert canvas is not None
        canvas.delete("anim")  # clear bars only — pill background stays
        center = (_BAR_COUNT - 1) / 2.0
        cy = _OVERLAY_H // 2
        for i in range(_BAR_COUNT):
            # Gaussian envelope: 1.0 at center, ~0.18 at edges (sigma tuned to taste)
            dist = abs(i - center) / center
            envelope = math.exp(-dist * dist * 1.6)

            # Small symmetric phase offset — natural micro-variation, not a sweep
            phase = (i - center) * 0.35

            # Idle: gentle slow breathing shaped by envelope
            idle = envelope * 0.14 * (1.0 + math.sin(t * 2.2 + phase))

            # Voice: fast reaction shaped by envelope (center always wins)
            voice = normalized * envelope * (0.65 + 0.35 * math.sin(t * 14.0 + phase))

            strength = max(idle, voice)
            target = _BAR_MIN_H + (_BAR_MAX_H - _BAR_MIN_H) * strength
            self._bar_heights[i] += (target - self._bar_heights[i]) * 0.45
            h = self._bar_heights[i]

            x0 = _PAD_X + i * (_BAR_W + _BAR_GAP)
            canvas.create_rectangle(
                x0, int(cy - h / 2), x0 + _BAR_W, int(cy + h / 2),
                fill="#FFFFFF", outline="", tags="anim",
            )

    def _draw_transcribing_frame(self) -> None:
        """Slow traveling sine wave — calm 'thinking' state.

        Same 9 bars as recording but at lower amplitude and dimmer color so
        it reads clearly as 'processing' rather than 'listening'. The wave
        travels left→right continuously.  Bars interpolate smoothly from
        wherever recording left them.
        """
        t = _time.monotonic()
        canvas = self._canvas
        assert canvas is not None
        canvas.delete("anim")
        cy = _OVERLAY_H // 2

        _AMP = _BAR_MAX_H * 0.30          # max wave height ≈ 8 px
        _SPEED = 3.8                       # rad/s  (~0.6 Hz, slow and calm)
        _WAVE_K = 2 * math.pi / (_BAR_COUNT - 1)  # one full wavelength across bars

        for i in range(_BAR_COUNT):
            wave = 0.5 + 0.5 * math.sin(t * _SPEED - i * _WAVE_K)
            target = _BAR_MIN_H + _AMP * wave
            self._bar_heights[i] += (target - self._bar_heights[i]) * 0.25
            h = self._bar_heights[i]

            # Bar color tracks the wave crest: bright at peak, dim at trough
            gray = int(80 + 120 * wave)    # 80→200, never full white
            color = f"#{gray:02x}{gray:02x}{gray:02x}"

            x0 = _PAD_X + i * (_BAR_W + _BAR_GAP)
            canvas.create_rectangle(
                x0, int(cy - h / 2), x0 + _BAR_W, int(cy + h / 2),
                fill=color, outline="", tags="anim",
            )

    # ── silent toast ──────────────────────────────────────────────────────────

    def toast(self, text: str) -> None:
        if not self._cfg.get("notifications_enabled", True):
            return
        self.root.after(0, self._show_toast, text)

    def _show_toast(self, text: str) -> None:
        if self._toast is None:
            self._toast = tk.Toplevel(self.root)
            self._toast.overrideredirect(True)
            self._toast.attributes("-topmost", True)
            self._toast.configure(bg="#2a2a2a")
            self._toast_label = tk.Label(
                self._toast, font=("Segoe UI", 10), fg="#e8e8e8", bg="#2a2a2a", padx=16, pady=8
            )
            self._toast_label.pack()
        self._toast_label.config(text=text)
        self._toast.deiconify()
        self._position(self._toast, y_from_bottom=60, x_from_right=24)
        self._toast.after(1500, self._toast.withdraw)

    # ── settings dialog ─────────────────────────────────────────────────────────

    def open_settings(self) -> None:
        self.root.after(0, self._open_settings)

    def _open_settings(self) -> None:  # noqa: C901 (complexity — intentional, all one dialog)
        win = tk.Toplevel(self.root)
        win.title("VoiceFlow Settings")
        win.geometry("520x540")
        win.minsize(460, 460)
        win.resizable(True, True)
        win.transient(self.root)
        win.grab_set()

        outer = ttk.Frame(win, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        nb = ttk.Notebook(outer)
        nb.grid(row=0, column=0, sticky="nsew")

        # ── Tab: API ──────────────────────────────────────────────────────────
        tab_api = ttk.Frame(nb, padding=12)
        nb.add(tab_api, text="API")

        backend_var = tk.StringVar(value=self._cfg.get("backend", "openai"))
        key_var = tk.StringVar(value=self._cfg.get("openai_api_key", ""))
        model_var = tk.StringVar(value=self._cfg.get("model", _MODELS[0]))
        local_model_var = tk.StringVar(value=self._cfg.get("local_model", "small.en"))

        ttk.Label(tab_api, text="Transcription backend").pack(anchor="w")
        _rb = ttk.Frame(tab_api)
        _rb.pack(anchor="w", pady=(2, 8))
        ttk.Radiobutton(_rb, text="Cloud — OpenAI", variable=backend_var, value="openai",
                        command=lambda: _switch_api()).pack(side="left")
        ttk.Radiobutton(_rb, text="Local — Whisper (free, private)", variable=backend_var,
                        value="local", command=lambda: _switch_api()).pack(side="left", padx=(16, 0))
        ttk.Separator(tab_api, orient="horizontal").pack(fill="x", pady=(0, 8))

        # OpenAI section
        _openai_sec = ttk.Frame(tab_api)
        ttk.Label(_openai_sec, text="OpenAI API key").pack(anchor="w")
        ttk.Entry(_openai_sec, textvariable=key_var, show="*", width=46).pack(fill="x", pady=(2, 10))
        ttk.Label(_openai_sec, text="Transcription model").pack(anchor="w")
        ttk.Combobox(_openai_sec, textvariable=model_var, values=_MODELS, state="readonly", width=32).pack(
            anchor="w", pady=(2, 0)
        )

        # Local section
        _local_sec = ttk.Frame(tab_api)
        _lm_row = ttk.Frame(_local_sec)
        _lm_row.pack(anchor="w", pady=(0, 4))
        ttk.Label(_lm_row, text="Model:").pack(side="left")
        _lm_combo = ttk.Combobox(_lm_row, textvariable=local_model_var,
                                 values=_LOCAL_MODEL_SIZES, state="readonly", width=18)
        _lm_combo.pack(side="left", padx=(6, 0))
        _lm_size_lbl = ttk.Label(_lm_row, foreground="#666")
        _lm_size_lbl.pack(side="left", padx=8)
        _lm_status_lbl = ttk.Label(_local_sec)
        _lm_status_lbl.pack(anchor="w", pady=(0, 4))
        _lm_btn_row = ttk.Frame(_local_sec)
        _lm_btn_row.pack(anchor="w")
        _lm_dl_btn = ttk.Button(_lm_btn_row, text="Download model",
                                command=lambda: _start_local_dl())
        _lm_dl_btn.pack(side="left")
        _lm_rm_btn = ttk.Button(_lm_btn_row, text="Remove",
                                command=lambda: _remove_local())
        _lm_rm_btn.pack(side="left", padx=(8, 0))
        _lm_prog_frame = ttk.Frame(_local_sec)
        _lm_prog = ttk.Progressbar(_lm_prog_frame, mode="determinate", length=300)
        _lm_prog.pack(fill="x")
        _lm_prog_lbl = ttk.Label(_lm_prog_frame, text="", foreground="#666")
        _lm_prog_lbl.pack(anchor="w")
        _lm_err_lbl = ttk.Label(_local_sec, foreground="#cc0000", wraplength=360)

        def _refresh_lm(*_):
            from voiceflow import model_manager
            name = local_model_var.get()
            _lm_size_lbl.config(
                text=f"· {model_manager.MODEL_SIZES.get(name,'?')} — {model_manager.MODEL_DESCS.get(name,'')}"
            )
            if model_manager.is_cached(name):
                _lm_status_lbl.config(text="✓ Downloaded", foreground="#2a8a2a")
                _lm_dl_btn.config(text="Re-download")
                _lm_rm_btn.config(state="normal")
            else:
                _lm_status_lbl.config(text="Not downloaded yet", foreground="#cc0000")
                _lm_dl_btn.config(text="Download model")
                _lm_rm_btn.config(state="disabled")

        _lm_combo.bind("<<ComboboxSelected>>", _refresh_lm)

        def _remove_local():
            name = local_model_var.get()
            size = None
            try:
                from voiceflow import model_manager
                size = model_manager.MODEL_SIZES.get(name, "")
            except Exception:
                pass
            if not messagebox.askyesno(
                "Remove model",
                f"Delete the downloaded '{name}' model ({size}) from disk?\n\n"
                "You can re-download it anytime.",
                parent=win,
            ):
                return
            _lm_err_lbl.pack_forget()
            try:
                from voiceflow import model_manager, transcriber_local
                # Drop any in-RAM model first so its files aren't locked (Windows).
                transcriber_local.reset_model()
                removed = model_manager.delete(name)
            except Exception as exc:
                _lm_err_lbl.config(text=f"Remove failed: {exc}")
                _lm_err_lbl.pack(anchor="w", pady=(4, 0))
                return
            if removed:
                _lm_status_lbl.config(text="Removed", foreground="#666")
            _refresh_lm()

        def _start_local_dl():
            import threading as _th
            name = local_model_var.get()
            _lm_dl_btn.config(state="disabled")
            _lm_combo.config(state="disabled")
            _lm_err_lbl.pack_forget()
            _lm_prog_frame.pack(fill="x", pady=(4, 0))
            _lm_prog.config(value=0, maximum=1, mode="determinate")
            _lm_prog_lbl.config(text="Connecting...")
            _lm_status_lbl.config(text="Downloading...", foreground="#666")

            def _do():
                try:
                    from voiceflow import model_manager

                    def _prog(done: int, total: int) -> None:
                        def _u():
                            _lm_prog.config(maximum=total, value=done)
                            _lm_prog_lbl.config(text=f"{done}/{total} files")
                        win.after(0, _u)

                    model_manager.download(name, _prog)

                    def _done():
                        _lm_prog_frame.pack_forget()
                        _lm_status_lbl.config(text="✓ Downloaded", foreground="#2a8a2a")
                        _lm_dl_btn.config(state="normal", text="Re-download")
                        _lm_combo.config(state="readonly")
                    win.after(0, _done)
                except Exception as exc:
                    def _err(e=exc):
                        _lm_prog_frame.pack_forget()
                        _lm_err_lbl.config(text=f"Download failed: {e}")
                        _lm_err_lbl.pack(anchor="w", pady=(4, 0))
                        _lm_status_lbl.config(text="Download failed", foreground="#cc0000")
                        _lm_dl_btn.config(state="normal")
                        _lm_combo.config(state="readonly")
                    win.after(0, _err)

            _th.Thread(target=_do, daemon=True, name="model-dl-settings").start()

        def _switch_api():
            if backend_var.get() == "openai":
                _local_sec.pack_forget()
                _openai_sec.pack(fill="x")
            else:
                _openai_sec.pack_forget()
                _local_sec.pack(fill="x")
                _refresh_lm()

        _switch_api()  # show correct section on open

        # ── Tab: Recording ────────────────────────────────────────────────────
        tab_rec = ttk.Frame(nb, padding=12)
        nb.add(tab_rec, text="Recording")

        lang_var = tk.StringVar(value=self._cfg.get("language", ""))
        dev_info = _query_input_devices()
        dev_names = [d[1] for d in dev_info]
        dev_idx_by_name = {d[1]: d[0] for d in dev_info}

        cur_dev_idx = self._cfg.get("input_device")
        cur_dev_name = _SYSTEM_DEFAULT_DEV
        if cur_dev_idx is not None:
            for idx, name in dev_info:
                if idx == cur_dev_idx:
                    cur_dev_name = name
                    break
        dev_var = tk.StringVar(value=cur_dev_name)

        ttk.Label(tab_rec, text="Input device").pack(anchor="w")
        ttk.Combobox(tab_rec, textvariable=dev_var, values=dev_names, state="readonly", width=40).pack(
            fill="x", pady=(2, 10)
        )
        ttk.Label(tab_rec, text="Language hint (ISO-639-1, e.g. en, hi — blank = auto)").pack(anchor="w")
        ttk.Entry(tab_rec, textvariable=lang_var, width=12).pack(anchor="w", pady=(2, 0))

        # ── Tab: Behavior ─────────────────────────────────────────────────────
        tab_beh = ttk.Frame(nb, padding=12)
        nb.add(tab_beh, text="Behavior")

        paste_mode_var = tk.StringVar(value=self._cfg.get("paste_mode", "clipboard"))
        voice_var = tk.BooleanVar(value=bool(self._cfg.get("voice_commands", False)))
        code_var = tk.BooleanVar(value=bool(self._cfg.get("code_mode", False)))
        raw_var = tk.BooleanVar(value=bool(self._cfg.get("raw_mode", False)))
        preserve_var = tk.BooleanVar(value=bool(self._cfg.get("preserve_clipboard", False)))

        ttk.Label(tab_beh, text="Paste method").pack(anchor="w")
        ttk.Combobox(
            tab_beh, textvariable=paste_mode_var,
            values=["clipboard", "type"], state="readonly", width=14,
        ).pack(anchor="w", pady=(2, 0))
        ttk.Label(
            tab_beh,
            text="  clipboard — Ctrl+V (default)\n  type — character-by-character (for apps that block Ctrl+V)",
            foreground="#666666", justify="left",
        ).pack(anchor="w", pady=(2, 10))
        ttk.Checkbutton(tab_beh, text='Voice commands ("comma", "new line", …)', variable=voice_var).pack(anchor="w")
        ttk.Checkbutton(tab_beh, text="Code mode (no auto-capitalize, no trailing period)", variable=code_var).pack(anchor="w")
        ttk.Checkbutton(tab_beh, text="Raw mode (verbatim transcript, skip all cleaning)", variable=raw_var).pack(anchor="w")
        ttk.Checkbutton(tab_beh, text="Preserve clipboard (restore prior clipboard after paste)", variable=preserve_var).pack(anchor="w")

        # ── Tab: Text ─────────────────────────────────────────────────────────
        tab_txt = ttk.Frame(nb, padding=12)
        nb.add(tab_txt, text="Text")
        tab_txt.columnconfigure(0, weight=1)
        tab_txt.rowconfigure(2, weight=1)

        extra_var = tk.StringVar(value=", ".join(self._cfg.get("extra_fillers", [])))

        ttk.Label(tab_txt, text="Extra fillers to strip (comma-separated)").grid(row=0, column=0, sticky="w")
        ttk.Entry(tab_txt, textvariable=extra_var, width=46).grid(row=1, column=0, sticky="we", pady=(2, 10))

        ttk.Label(tab_txt, text='Dictionary — JSON {"spoken word": "Replacement"}').grid(row=2, column=0, sticky="w")
        dict_outer = ttk.Frame(tab_txt)
        dict_outer.grid(row=3, column=0, sticky="nsew", pady=(2, 0))
        dict_outer.columnconfigure(0, weight=1)
        dict_outer.rowconfigure(0, weight=1)
        dict_text = tk.Text(dict_outer, width=46, height=7, font=("Courier New", 9), wrap="none", undo=True)
        dict_scroll_y = ttk.Scrollbar(dict_outer, command=dict_text.yview)
        dict_text.configure(yscrollcommand=dict_scroll_y.set)
        dict_scroll_y.grid(row=0, column=1, sticky="ns")
        dict_text.grid(row=0, column=0, sticky="nsew")
        dict_text.insert("1.0", json.dumps(self._cfg.get("dictionary", {}), indent=2, ensure_ascii=False))

        # ── Footer (always-visible app prefs) ─────────────────────────────────
        ttk.Separator(outer).grid(row=1, column=0, sticky="we", pady=(10, 6))

        notif_var = tk.BooleanVar(value=bool(self._cfg.get("notifications_enabled", True)))
        startup_var = tk.BooleanVar(value=bool(self._cfg.get("start_on_login", True)))
        footer = ttk.Frame(outer)
        footer.grid(row=2, column=0, sticky="we")
        ttk.Checkbutton(footer, text="Show notifications", variable=notif_var).pack(side="left")
        ttk.Checkbutton(footer, text="Start on login", variable=startup_var).pack(side="left", padx=(16, 0))

        # ── Buttons ───────────────────────────────────────────────────────────
        btns = ttk.Frame(outer)
        btns.grid(row=3, column=0, sticky="we", pady=(8, 0))

        def save() -> None:
            if backend_var.get() == "local":
                from voiceflow import model_manager
                if not model_manager.is_cached(local_model_var.get()):
                    messagebox.showwarning(
                        "Model not downloaded",
                        f"The '{local_model_var.get()}' model hasn't been downloaded yet.\n"
                        "Please click 'Download model' in the API tab before saving.",
                        parent=win,
                    )
                    nb.select(tab_api)
                    return

            raw_dict = dict_text.get("1.0", "end").strip()
            try:
                dict_val = json.loads(raw_dict or "{}")
                if not isinstance(dict_val, dict):
                    raise ValueError("must be a JSON object")
                for k, v in dict_val.items():
                    if not isinstance(k, str) or not isinstance(v, str):
                        raise ValueError(f"key {k!r} and value must both be strings")
            except (json.JSONDecodeError, ValueError) as exc:
                messagebox.showerror("Dictionary error", str(exc), parent=win)
                nb.select(tab_txt)
                return

            extra_raw = extra_var.get().strip()
            extra_list = [f.strip() for f in extra_raw.split(",") if f.strip()] if extra_raw else []

            chosen = dev_idx_by_name.get(dev_var.get(), -1)
            input_device = None if chosen == -1 else chosen

            self._cfg.update(
                backend=backend_var.get(),
                local_model=local_model_var.get(),
                openai_api_key=key_var.get().strip(),
                model=model_var.get(),
                language=lang_var.get().strip(),
                input_device=input_device,
                paste_mode=paste_mode_var.get(),
                voice_commands=voice_var.get(),
                code_mode=code_var.get(),
                raw_mode=raw_var.get(),
                preserve_clipboard=preserve_var.get(),
                extra_fillers=extra_list,
                dictionary=dict_val,
                notifications_enabled=notif_var.get(),
                start_on_login=startup_var.get(),
            )
            self._startup_var.set(self._cfg["start_on_login"])
            self._on_settings_saved(self._cfg)
            win.destroy()

        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text="Save", command=save).pack(side="right")

    # ── setup wizard (first-run) ──────────────────────────────────────────────

    def open_setup_wizard(self, on_complete: Callable[[dict], None]) -> None:
        self.root.after(0, self._open_setup_wizard, on_complete)

    def _open_setup_wizard(self, on_complete: Callable[[dict], None]) -> None:  # noqa: C901
        import threading as _th
        win = tk.Toplevel(self.root)
        win.title("VoiceFlow Setup")
        win.geometry("480x360")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()
        win.protocol("WM_DELETE_WINDOW", lambda: None)  # must complete wizard

        cfg_out: dict = {}
        backend_var = tk.StringVar(value="openai")

        def _show(frame: ttk.Frame) -> None:
            for f in (p_choose, p_openai, p_local):
                f.pack_forget()
            frame.pack(fill="both", expand=True)

        # ── Page 1: choose backend ─────────────────────────────────────
        p_choose = ttk.Frame(win, padding=24)

        ttk.Label(p_choose, text="Welcome to VoiceFlow",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(p_choose,
                  text="How would you like to transcribe your voice?").pack(anchor="w", pady=(4, 16))

        for _val, _title, _sub in [
            ("openai", "Cloud — OpenAI",
             "Fast & accurate. Needs an API key. ~$0.006/min."),
            ("local", "Local — Whisper  (free, private)",
             "Runs on your PC. No API key needed.\nOne-time model download (75 MB – 3 GB)."),
        ]:
            _row = ttk.Frame(p_choose)
            _row.pack(fill="x", pady=4)
            ttk.Radiobutton(_row, variable=backend_var, value=_val).pack(
                side="left", anchor="n", pady=2)
            _txt = ttk.Frame(_row)
            _txt.pack(side="left", padx=8)
            ttk.Label(_txt, text=_title, font=("Segoe UI", 10, "bold")).pack(anchor="w")
            ttk.Label(_txt, text=_sub, foreground="#666", justify="left").pack(anchor="w")

        def _on_continue():
            if backend_var.get() == "openai":
                _show(p_openai)
            else:
                _show(p_local)
                _refresh_local()

        _nav1 = ttk.Frame(p_choose)
        _nav1.pack(side="bottom", fill="x")
        ttk.Button(_nav1, text="Continue →", command=_on_continue).pack(side="right")

        # ── Page 2a: OpenAI key ────────────────────────────────────────
        p_openai = ttk.Frame(win, padding=24)

        ttk.Label(p_openai, text="OpenAI API key",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(p_openai, text="Stored locally. Sent only to OpenAI.",
                  foreground="#666").pack(anchor="w", pady=(2, 12))
        key_var = tk.StringVar()
        ttk.Entry(p_openai, textvariable=key_var, show="*", width=44).pack(fill="x")
        ttk.Label(p_openai, text="Get your key at platform.openai.com",
                  foreground="#0066cc").pack(anchor="w", pady=(4, 0))

        def _finish_openai():
            key = key_var.get().strip()
            if not key:
                messagebox.showwarning(
                    "API key required", "Please enter your OpenAI API key.", parent=win)
                return
            cfg_out.update(backend="openai", openai_api_key=key)
            win.destroy()
            on_complete(cfg_out)

        _nav2a = ttk.Frame(p_openai)
        _nav2a.pack(side="bottom", fill="x")
        ttk.Button(_nav2a, text="← Back", command=lambda: _show(p_choose)).pack(side="left")
        ttk.Button(_nav2a, text="Finish", command=_finish_openai).pack(side="right")

        # ── Page 2b: local model download ──────────────────────────────
        p_local = ttk.Frame(win, padding=24)

        ttk.Label(p_local, text="Choose Whisper model",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w")

        from voiceflow import model_manager as _mm
        _recommended = _mm.recommended_model()

        _lm_pick_row = ttk.Frame(p_local)
        _lm_pick_row.pack(anchor="w", pady=(8, 4))
        _local_model_var = tk.StringVar(value=_recommended)
        _lm_cb = ttk.Combobox(_lm_pick_row, textvariable=_local_model_var,
                              values=_LOCAL_MODEL_SIZES, state="readonly", width=18)
        _lm_cb.pack(side="left")
        _lm_desc = ttk.Label(_lm_pick_row, foreground="#666")
        _lm_desc.pack(side="left", padx=8)

        ttk.Label(
            p_local,
            text=f"✓ Recommended for your PC ({os.cpu_count() or '?'} CPU cores): {_recommended}",
            foreground="#2a8a2a",
        ).pack(anchor="w", pady=(0, 2))

        _lm_stat = ttk.Label(p_local)
        _lm_stat.pack(anchor="w", pady=(0, 6))

        _lm_dl_btn = ttk.Button(p_local, text="Download model",
                                command=lambda: _start_dl())
        _lm_dl_btn.pack(anchor="w")

        _lm_pf = ttk.Frame(p_local)
        _lm_pb = ttk.Progressbar(_lm_pf, length=380, mode="determinate")
        _lm_pb.pack(fill="x")
        _lm_plbl = ttk.Label(_lm_pf, text="", foreground="#666")
        _lm_plbl.pack(anchor="w")

        _lm_err = ttk.Label(p_local, foreground="#cc0000", wraplength=400)

        def _refresh_local(*_) -> None:
            from voiceflow import model_manager
            name = _local_model_var.get()
            _lm_desc.config(
                text=f"· {model_manager.MODEL_SIZES.get(name,'?')} "
                     f"— {model_manager.MODEL_DESCS.get(name,'')}"
            )
            if model_manager.is_cached(name):
                _lm_stat.config(text="✓ Already downloaded", foreground="#2a8a2a")
                _lm_dl_btn.config(text="Re-download")
                _finish_btn.config(state="normal")
            else:
                _lm_stat.config(
                    text="Not downloaded yet — click Download below.", foreground="#999")
                _lm_dl_btn.config(text="Download model")
                _finish_btn.config(state="disabled")

        _lm_cb.bind("<<ComboboxSelected>>", _refresh_local)

        def _start_dl() -> None:
            name = _local_model_var.get()
            _lm_dl_btn.config(state="disabled")
            _lm_cb.config(state="disabled")
            _lm_err.pack_forget()
            _lm_pf.pack(fill="x", pady=(4, 0))
            _lm_pb.config(value=0, maximum=1, mode="determinate")
            _lm_plbl.config(text="Connecting to download server...")
            _lm_stat.config(text="Downloading...", foreground="#666")
            _finish_btn.config(state="disabled")

            def _do() -> None:
                try:
                    from voiceflow import model_manager

                    def _prog(done: int, total: int) -> None:
                        def _u():
                            _lm_pb.config(maximum=total, value=done)
                            _lm_plbl.config(text=f"Downloading... {done}/{total} files")
                        win.after(0, _u)

                    model_manager.download(name, _prog)

                    def _switch_to_loading():
                        _lm_pb.config(mode="indeterminate")
                        _lm_pb.start(15)
                        _lm_plbl.config(text="Loading model into memory...")
                    win.after(0, _switch_to_loading)

                    from voiceflow import transcriber_local
                    transcriber_local._load_model(name)

                    def _done():
                        _lm_pb.stop()
                        _lm_pf.pack_forget()
                        _lm_stat.config(text="✓ Ready!", foreground="#2a8a2a")
                        _lm_dl_btn.config(state="normal", text="Re-download")
                        _lm_cb.config(state="readonly")
                        _finish_btn.config(state="normal")
                    win.after(0, _done)

                except Exception as exc:
                    def _err(e=exc):
                        _lm_pb.stop()
                        _lm_pf.pack_forget()
                        _lm_err.config(text=f"Download failed: {e}")
                        _lm_err.pack(anchor="w", pady=(4, 0))
                        _lm_stat.config(text="Download failed", foreground="#cc0000")
                        _lm_dl_btn.config(state="normal")
                        _lm_cb.config(state="readonly")
                    win.after(0, _err)

            _th.Thread(target=_do, daemon=True, name="wizard-model-dl").start()

        def _finish_local():
            cfg_out.update(backend="local", local_model=_local_model_var.get())
            win.destroy()
            on_complete(cfg_out)

        _nav2b = ttk.Frame(p_local)
        _nav2b.pack(side="bottom", fill="x")
        ttk.Button(_nav2b, text="← Back", command=lambda: _show(p_choose)).pack(side="left")
        _finish_btn = ttk.Button(_nav2b, text="Finish", command=_finish_local, state="disabled")
        _finish_btn.pack(side="right")

        _show(p_choose)
        win.focus_set()

    # ── window visibility + lifecycle ──────────────────────────────────────────

    def show_window(self) -> None:
        self.root.after(0, lambda: (self.root.deiconify(), self.root.lift()))

    def hide(self) -> None:
        self.root.withdraw()

    def run(self) -> None:
        self.root.mainloop()

    def stop(self) -> None:
        self.root.after(0, self.root.destroy)

    # ── helpers ──────────────────────────────────────────────────────────────

    def _position(self, win: tk.Toplevel, y_from_bottom: int, x_from_right: int | None = None) -> None:
        win.update_idletasks()
        w, h = win.winfo_width(), win.winfo_height()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x = (sw - w) // 2 if x_from_right is None else sw - w - x_from_right
        y = sh - h - y_from_bottom
        win.geometry(f"+{x}+{y}")
