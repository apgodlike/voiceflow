"""System tray icon + menu using pystray + Pillow."""
import argparse
import threading
import time
from typing import Literal

from PIL import Image, ImageDraw
import pystray

# 16x16 solid-circle icons — generated inline (no external image files)
_ICON_COLORS: dict[str, str] = {
    "idle": "#808080",       # gray
    "recording": "#e03030",  # red
    "transcribing": "#e0a000",  # yellow
    "failed": "#e06000",     # orange
}


def _make_icon(color: str) -> Image.Image:
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, 13, 13], fill=color)
    return img


class Tray:
    def __init__(self, on_quit=None, on_retry=None) -> None:
        self._state: Literal["idle", "recording", "transcribing"] = "idle"
        self._failed_count = 0
        self._lock = threading.Lock()
        self._on_quit_cb = on_quit
        self._on_retry_cb = on_retry
        self._icon = pystray.Icon(
            "VoiceFlow",
            _make_icon(_ICON_COLORS["idle"]),
            "VoiceFlow",
            menu=pystray.Menu(self._build_menu),
        )

    # ── public API ────────────────────────────────────────────────────────────

    def set_state(self, state: Literal["idle", "recording", "transcribing"]) -> None:
        with self._lock:
            self._state = state
        color = _ICON_COLORS.get(state, _ICON_COLORS["idle"])
        try:
            self._icon.icon = _make_icon(color)
            self._icon.title = f"VoiceFlow — {state}"
        except OSError:
            pass

    def set_failed_count(self, n: int) -> None:
        with self._lock:
            self._failed_count = n
        if n > 0:
            try:
                self._icon.icon = _make_icon(_ICON_COLORS["failed"])
            except OSError:
                pass

    def notify(self, title: str, message: str) -> None:
        try:
            self._icon.notify(message, title)
        except Exception:
            pass

    def run(self) -> None:
        self._icon.run()

    def run_detached(self) -> None:
        self._icon.run_detached()

    def stop(self) -> None:
        self._icon.stop()

    # ── internal ──────────────────────────────────────────────────────────────

    def _build_menu(self) -> tuple:
        with self._lock:
            state = self._state
            failed = self._failed_count

        items: list[pystray.MenuItem] = [
            pystray.MenuItem(f"Status: {state}", None, enabled=False),
            pystray.Menu.SEPARATOR,
        ]

        retry_label = f"Retry Failed ({failed})" if failed else "No Failed Jobs"
        items.append(pystray.MenuItem(retry_label, self._on_retry, enabled=failed > 0))
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("Quit", self._on_quit))

        return tuple(items)

    def _on_retry(self, icon, item) -> None:
        if self._on_retry_cb:
            self._on_retry_cb()

    def _on_quit(self, icon, item) -> None:
        if self._on_quit_cb:
            self._on_quit_cb()
        self._icon.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        tray = Tray()

        def cycle():
            states = ["idle", "recording", "transcribing", "idle"]
            for s in states:
                print(f"State → {s}")
                tray.set_state(s)
                time.sleep(2)
            tray.set_failed_count(1)
            time.sleep(2)
            tray.stop()

        t = threading.Thread(target=cycle, daemon=True)
        t.start()
        tray.run()
        print("Tray test done.")
