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
import time as _time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable

from voiceflow import paths

logger = logging.getLogger("voiceflow.ui")

_COLORS = {"recording": "#e03030", "transcribing": "#e0a000", "idle": "#808080"}
_MODELS = ["gpt-4o-mini-transcribe", "gpt-4o-transcribe"]
_SYSTEM_DEFAULT_DEV = "System default"

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
    ) -> None:
        self._cfg = cfg
        self._on_settings_saved = on_settings_saved
        self._on_startup_toggle = on_startup_toggle

        self.root = tk.Tk()
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
        self._bar_heights: list[float] = [float(_BAR_MIN_H)] * _BAR_COUNT  # size = _BAR_COUNT

        self._toast: tk.Toplevel | None = None
        self._build_main()
        self.root.withdraw()  # start hidden — user opens via tray "Open VoiceFlow"

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

        key_var = tk.StringVar(value=self._cfg.get("openai_api_key", ""))
        model_var = tk.StringVar(value=self._cfg.get("model", _MODELS[0]))

        ttk.Label(tab_api, text="OpenAI API key").pack(anchor="w")
        ttk.Entry(tab_api, textvariable=key_var, show="*", width=46).pack(fill="x", pady=(2, 10))
        ttk.Label(tab_api, text="Transcription model").pack(anchor="w")
        ttk.Combobox(tab_api, textvariable=model_var, values=_MODELS, state="readonly", width=32).pack(
            anchor="w", pady=(2, 0)
        )

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
