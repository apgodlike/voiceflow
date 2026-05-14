"""Tests for paster.py — monkeypatched pyperclip + pyautogui."""
from unittest.mock import call, patch

import pytest

from voiceflow.paster import copy_only, paste


def test_paste_copies_to_clipboard_then_hotkey():
    with patch("voiceflow.paster.pyperclip.copy") as mock_copy, \
         patch("voiceflow.paster.pyautogui.hotkey") as mock_hotkey:
        result = paste("hello world")

    mock_copy.assert_called_once_with("hello world")
    mock_hotkey.assert_called_once()
    assert result is True


def test_paste_clipboard_always_set_even_when_hotkey_fails():
    with patch("voiceflow.paster.pyperclip.copy") as mock_copy, \
         patch("voiceflow.paster.pyautogui.hotkey", side_effect=RuntimeError("blocked")):
        result = paste("fallback text")

    mock_copy.assert_called_once_with("fallback text")
    assert result is False


def test_copy_only_no_hotkey():
    with patch("voiceflow.paster.pyperclip.copy") as mock_copy, \
         patch("voiceflow.paster.pyautogui.hotkey") as mock_hotkey:
        copy_only("just copy")

    mock_copy.assert_called_once_with("just copy")
    mock_hotkey.assert_not_called()


def test_paste_uses_ctrl_v_on_windows():
    import sys
    with patch.object(sys, "platform", "win32"), \
         patch("voiceflow.paster.pyperclip.copy"), \
         patch("voiceflow.paster.pyautogui.hotkey") as mock_hotkey:
        paste("test")

    args = mock_hotkey.call_args[0]
    assert "ctrl" in args
    assert "v" in args
