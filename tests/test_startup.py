"""Tests for startup.py — winreg fully mocked, no real registry writes."""
import sys
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only")

from voiceflow import startup


def test_command_dev_mode():
    with patch.object(sys, "frozen", False, create=True):
        cmd = startup._win_command()
    assert "voiceflow.main" in cmd
    assert sys.executable in cmd


def test_command_frozen_mode():
    with patch.object(sys, "frozen", True, create=True):
        cmd = startup._win_command()
    assert "voiceflow.main" not in cmd
    assert sys.executable in cmd


def test_enable_writes_run_value():
    fake_winreg = MagicMock()
    fake_key = MagicMock()
    fake_winreg.OpenKey.return_value.__enter__.return_value = fake_key
    with patch.object(startup, "winreg", fake_winreg):
        startup.enable()
    fake_winreg.SetValueEx.assert_called_once()
    assert fake_winreg.SetValueEx.call_args[0][1] == "VoiceFlow"


def test_is_enabled_false_when_missing():
    fake_winreg = MagicMock()
    fake_winreg.OpenKey.return_value.__enter__.return_value = MagicMock()
    fake_winreg.QueryValueEx.side_effect = FileNotFoundError
    with patch.object(startup, "winreg", fake_winreg):
        assert startup.is_enabled() is False


def test_apply_routes_to_enable_or_disable():
    with patch.object(startup, "enable") as en, patch.object(startup, "disable") as dis:
        startup.apply(True)
        startup.apply(False)
    en.assert_called_once()
    dis.assert_called_once()
