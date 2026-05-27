"""Tests for paster.py — monkeypatched pyperclip + pyautogui."""
from unittest.mock import call, patch

import pytest

from voiceflow.paster import paste


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


def test_paste_uses_ctrl_v_on_windows():
    import sys
    with patch.object(sys, "platform", "win32"), \
         patch("voiceflow.paster.pyperclip.copy"), \
         patch("voiceflow.paster.pyautogui.hotkey") as mock_hotkey:
        paste("test")

    args = mock_hotkey.call_args[0]
    assert "ctrl" in args
    assert "v" in args


def test_preserve_clipboard_restores_prior_after_success():
    with patch("voiceflow.paster.pyperclip.paste", return_value="OLD") as mock_read, \
         patch("voiceflow.paster.pyperclip.copy") as mock_copy, \
         patch("voiceflow.paster.pyautogui.hotkey"), \
         patch("voiceflow.paster.time.sleep"):
        result = paste("dictated", preserve_clipboard=True)

    mock_read.assert_called_once()
    # first copy delivers the text, second restores the prior clipboard
    assert mock_copy.call_args_list == [call("dictated"), call("OLD")]
    assert result is True


def test_preserve_clipboard_does_not_restore_on_paste_failure():
    with patch("voiceflow.paster.pyperclip.paste", return_value="OLD"), \
         patch("voiceflow.paster.pyperclip.copy") as mock_copy, \
         patch("voiceflow.paster.pyautogui.hotkey", side_effect=RuntimeError("blocked")), \
         patch("voiceflow.paster.time.sleep"):
        result = paste("dictated", preserve_clipboard=True)

    # only the text copy — prior NOT restored, so text stays recoverable
    mock_copy.assert_called_once_with("dictated")
    assert result is False


def test_preserve_clipboard_off_does_not_read_clipboard():
    with patch("voiceflow.paster.pyperclip.paste") as mock_read, \
         patch("voiceflow.paster.pyperclip.copy") as mock_copy, \
         patch("voiceflow.paster.pyautogui.hotkey"):
        paste("dictated")

    mock_read.assert_not_called()
    mock_copy.assert_called_once_with("dictated")
