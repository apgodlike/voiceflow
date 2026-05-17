"""System tray icon + menu using pystray + Pillow."""
import argparse
import sqlite3
import threading
import time
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw
import pystray

from voiceflow import queue as q

_DB_PATH = Path(__file__).parent.parent / "data" / "history.sqlite"

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


def _last_10_history(db_path: Path = _DB_PATH) -> list[tuple[str, str]]:
    if not db_path.exists():
        return []
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT id, cleaned_text FROM history ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
        return rows
    except Exception:
        return []


class Tray:
    def __init__(self, db_path: Path = _DB_PATH, on_quit=None) -> None:
        self._state: Literal["idle", "recording", "transcribing"] = "idle"
        self._failed_count = 0
        self._db_path = db_path
        self._lock = threading.Lock()
        self._on_quit_cb = on_quit
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

        history = _last_10_history(self._db_path)
        if history:
            items.append(
                pystray.MenuItem(
                    "History",
                    pystray.Menu(
                        *[
                            pystray.MenuItem(
                                f"{text[:40]}{'…' if len(text) > 40 else ''}",
                                None,
                                enabled=False,
                            )
                            for _, text in history
                        ]
                    ),
                )
            )

        retry_label = f"Retry Failed ({failed})" if failed else "No Failed Jobs"
        items.append(pystray.MenuItem(retry_label, self._on_retry, enabled=failed > 0))
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("Quit", self._on_quit))

        return tuple(items)

    def _on_retry(self, icon, item) -> None:
        pass  # main.py sweeper handles retries; menu entry is informational trigger

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
