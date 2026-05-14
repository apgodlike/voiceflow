"""Tests for hotkey.py state machine — driven directly, no pynput listener."""
import time
import threading
from unittest.mock import MagicMock

import pytest
from pynput import keyboard

from voiceflow.hotkey import (
    DOUBLE_TAP_WINDOW_MS,
    HOLD_DEBOUNCE_MS,
    _CTRL,
    _ALT,
    _STATE_HOLD,
    _STATE_IDLE,
    _STATE_TOGGLE,
    _StateMachine,
)

_HOLD_S = (HOLD_DEBOUNCE_MS + 50) / 1000
_TAP_S = (DOUBLE_TAP_WINDOW_MS - 50) / 1000


def make_sm():
    on_start = MagicMock()
    on_stop = MagicMock()
    sm = _StateMachine(on_start, on_stop)
    return sm, on_start, on_stop


def both_down(sm):
    sm.key_press(_CTRL)
    sm.key_press(_ALT)


def both_up(sm):
    sm.key_release(_CTRL)
    sm.key_release(_ALT)


# ── hold mode ────────────────────────────────────────────────────────────────

def test_hold_mode_fires_start_after_debounce():
    sm, on_start, on_stop = make_sm()
    both_down(sm)
    time.sleep(_HOLD_S)
    assert sm._state == _STATE_HOLD
    on_start.assert_called_once()


def test_hold_mode_fires_stop_on_release():
    sm, on_start, on_stop = make_sm()
    both_down(sm)
    time.sleep(_HOLD_S)
    both_up(sm)
    assert sm._state == _STATE_IDLE
    on_stop.assert_called_once()


def test_hold_debounce_rejected_on_quick_release():
    sm, on_start, on_stop = make_sm()
    both_down(sm)
    time.sleep(0.05)  # less than 200 ms
    both_up(sm)
    time.sleep(_HOLD_S)  # wait past debounce window
    on_start.assert_not_called()
    assert sm._state == _STATE_IDLE


# ── double-tap toggle ─────────────────────────────────────────────────────────

def test_double_tap_starts_recording():
    sm, on_start, on_stop = make_sm()
    both_down(sm)
    both_up(sm)
    time.sleep(_TAP_S)
    both_down(sm)
    assert sm._state == _STATE_TOGGLE
    on_start.assert_called_once()


def test_single_tap_stops_toggle():
    sm, on_start, on_stop = make_sm()
    # enter toggle
    both_down(sm)
    both_up(sm)
    time.sleep(_TAP_S)
    both_down(sm)
    assert sm._state == _STATE_TOGGLE
    # single tap stops
    both_up(sm)
    both_down(sm)
    assert sm._state == _STATE_IDLE
    on_stop.assert_called_once()


def test_double_tap_stops_toggle():
    sm, on_start, on_stop = make_sm()
    both_down(sm)
    both_up(sm)
    time.sleep(_TAP_S)
    both_down(sm)  # enter toggle
    both_up(sm)
    time.sleep(_TAP_S)
    both_down(sm)  # second press in toggle → stop
    assert sm._state == _STATE_IDLE
    on_stop.assert_called_once()


def test_no_double_tap_after_long_gap():
    sm, on_start, on_stop = make_sm()
    both_down(sm)
    both_up(sm)
    time.sleep((DOUBLE_TAP_WINDOW_MS + 100) / 1000)  # gap > window
    both_down(sm)
    # not a double tap — starts hold debounce, state still IDLE waiting for debounce
    assert sm._state == _STATE_IDLE
    time.sleep(_HOLD_S)
    assert sm._state == _STATE_HOLD


def test_irrelevant_keys_ignored():
    sm, on_start, on_stop = make_sm()
    sm.key_press(keyboard.Key.shift)
    sm.key_release(keyboard.Key.shift)
    on_start.assert_not_called()
    on_stop.assert_not_called()
    assert sm._state == _STATE_IDLE
