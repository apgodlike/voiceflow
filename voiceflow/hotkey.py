"""Hotkey state machine — hold-mode OR double-tap-toggle for Left Ctrl + Left Alt."""
import argparse
import os
import threading
import time
from typing import Callable

from pynput import keyboard

HOLD_DEBOUNCE_MS = 200
DOUBLE_TAP_WINDOW_MS = 400

_CTRL = keyboard.Key.ctrl_l
_ALT = keyboard.Key.alt_l

_STATE_IDLE = "IDLE"
_STATE_HOLD = "RECORDING_HOLD"
_STATE_TOGGLE = "RECORDING_TOGGLE"


class _StateMachine:
    """Pure state machine — no pynput dependency so tests can drive it directly."""

    def __init__(self, on_start: Callable, on_stop: Callable) -> None:
        self._on_start = on_start
        self._on_stop = on_stop
        self._state = _STATE_IDLE
        self._pressed: set = set()
        self._hold_timer: threading.Timer | None = None
        self._last_release_time: float = 0.0
        self._lock = threading.Lock()

    # ── public ──────────────────────────────────────────────────────────────

    def key_press(self, key) -> None:
        if key not in (_CTRL, _ALT):
            return
        with self._lock:
            self._pressed.add(key)
            if self._pressed >= {_CTRL, _ALT}:
                self._on_both_down()

    def key_release(self, key) -> None:
        if key not in (_CTRL, _ALT):
            return
        with self._lock:
            was_full = self._pressed >= {_CTRL, _ALT}
            self._pressed.discard(key)
            if was_full:
                self._on_either_up()

    # ── internals ────────────────────────────────────────────────────────────

    def _on_both_down(self) -> None:
        if self._state == _STATE_IDLE:
            now = time.monotonic()
            since_release = (now - self._last_release_time) * 1000
            if since_release < DOUBLE_TAP_WINDOW_MS and self._last_release_time > 0:
                # double-tap → toggle mode
                self._cancel_hold_timer()
                self._state = _STATE_TOGGLE
                self._on_start()
            else:
                # start hold debounce timer
                self._cancel_hold_timer()
                self._hold_timer = threading.Timer(
                    HOLD_DEBOUNCE_MS / 1000, self._hold_debounce_fired
                )
                self._hold_timer.start()
        elif self._state == _STATE_TOGGLE:
            # single or double tap in toggle → stop
            self._state = _STATE_IDLE
            self._on_stop()

    def _on_either_up(self) -> None:
        if self._state == _STATE_HOLD:
            self._cancel_hold_timer()
            self._state = _STATE_IDLE
            self._last_release_time = time.monotonic()
            self._on_stop()
        elif self._state == _STATE_IDLE:
            self._cancel_hold_timer()
            self._last_release_time = time.monotonic()

    def _hold_debounce_fired(self) -> None:
        with self._lock:
            if self._state == _STATE_IDLE and self._pressed >= {_CTRL, _ALT}:
                self._state = _STATE_HOLD
                self._on_start()

    def _cancel_hold_timer(self) -> None:
        if self._hold_timer is not None:
            self._hold_timer.cancel()
            self._hold_timer = None


class HotkeyController:
    def __init__(self, on_start: Callable, on_stop: Callable) -> None:
        self._sm = _StateMachine(on_start, on_stop)
        self._listener: keyboard.Listener | None = None

    def start(self) -> None:
        self._listener = keyboard.Listener(
            on_press=self._sm.key_press,
            on_release=self._sm.key_release,
        )
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener = None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        print("Hold Ctrl+Alt to record (hold mode), or double-tap to toggle.")
        print("Ctrl+C to exit.")

        def on_start():
            print("START")

        def on_stop():
            print("STOP")

        ctrl = HotkeyController(on_start, on_stop)
        ctrl.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            ctrl.stop()
