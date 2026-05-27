"""Start-on-login via the HKCU Run registry key (Windows only).

No admin rights needed — HKCU is per-user. The command differs between a frozen
PyInstaller exe and a dev ``python -m voiceflow.main`` run.
"""
import logging
import sys

logger = logging.getLogger("voiceflow.startup")

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "VoiceFlow"

if sys.platform == "win32":
    import winreg


def _command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" -m voiceflow.main'


def enable() -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _command())
    logger.info("Enabled start-on-login")


def disable() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _APP_NAME)
        logger.info("Disabled start-on-login")
    except FileNotFoundError:
        pass


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, _APP_NAME)
        return True
    except FileNotFoundError:
        return False


def apply(enabled: bool) -> None:
    enable() if enabled else disable()
