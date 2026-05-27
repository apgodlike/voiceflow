"""Tkinter UI: main window, recording overlay, silent toast, settings dialog.

All widgets share one ``Tk`` root that MUST own the main thread (Tk is not
thread-safe). Worker threads call the public methods, which marshal onto the Tk
thread via ``root.after``. pystray runs on its own detached thread, so the two
event loops do not fight.

No method here makes a sound — toasts are silent by design.
"""
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable

_COLORS = {"recording": "#e03030", "transcribing": "#e0a000", "idle": "#808080"}
_MODELS = ["gpt-4o-mini-transcribe", "gpt-4o-transcribe"]

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

        self._overlay: tk.Toplevel | None = None
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

    # ── recording overlay ─────────────────────────────────────────────────────

    def set_state(self, state: str) -> None:
        self.root.after(0, self._apply_state, state)

    def _apply_state(self, state: str) -> None:
        if state == "recording":
            self._overlay_show("●  Recording", _COLORS["recording"])
        elif state == "transcribing":
            self._overlay_show("Transcribing…", _COLORS["transcribing"])
        else:
            self._overlay_hide()

    def _overlay_show(self, text: str, color: str) -> None:
        if self._overlay is None:
            self._overlay = tk.Toplevel(self.root)
            self._overlay.overrideredirect(True)
            self._overlay.attributes("-topmost", True)
            self._overlay.configure(bg="#1e1e1e")
            self._overlay_label = tk.Label(
                self._overlay, font=("Segoe UI", 12, "bold"), bg="#1e1e1e", padx=20, pady=10
            )
            self._overlay_label.pack()
        self._overlay_label.config(text=text, fg=color)
        self._overlay.deiconify()
        self._position(self._overlay, y_from_bottom=120)

    def _overlay_hide(self) -> None:
        if self._overlay is not None:
            self._overlay.withdraw()

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

    def _open_settings(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("VoiceFlow Settings")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        key_var = tk.StringVar(value=self._cfg.get("openai_api_key", ""))
        model_var = tk.StringVar(value=self._cfg.get("model", _MODELS[0]))
        notif_var = tk.BooleanVar(value=bool(self._cfg.get("notifications_enabled", True)))
        startup_var = tk.BooleanVar(value=bool(self._cfg.get("start_on_login", True)))

        frm = ttk.Frame(win, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="OpenAI API key").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=key_var, show="*", width=40).grid(row=1, column=0, columnspan=2, sticky="we", pady=(0, 8))

        ttk.Label(frm, text="Model").grid(row=4, column=0, sticky="w")
        ttk.Combobox(frm, textvariable=model_var, values=_MODELS, state="readonly", width=28).grid(
            row=5, column=0, sticky="w", pady=(0, 8)
        )

        ttk.Checkbutton(frm, text="Show silent notifications", variable=notif_var).grid(row=6, column=0, sticky="w")
        ttk.Checkbutton(frm, text="Start when I log in", variable=startup_var).grid(row=7, column=0, sticky="w", pady=(0, 8))

        def save() -> None:
            self._cfg.update(
                openai_api_key=key_var.get().strip(),
                model=model_var.get(),
                notifications_enabled=notif_var.get(),
                start_on_login=startup_var.get(),
            )
            self._startup_var.set(self._cfg["start_on_login"])
            self._on_settings_saved(self._cfg)
            win.destroy()

        btns = ttk.Frame(frm)
        btns.grid(row=8, column=0, columnspan=2, sticky="e", pady=(8, 0))
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
