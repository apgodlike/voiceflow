"""Start-on-login, per-user, no admin rights.

- Windows: HKCU Run registry key (unchanged from the original behavior).
- macOS:  a LaunchAgent plist in ~/Library/LaunchAgents.
- Linux:  an XDG autostart .desktop file in ~/.config/autostart.

The launch command differs between a frozen PyInstaller exe and a dev / pip
``python -m voiceflow.main`` run.
"""
import logging
import sys
from pathlib import Path

logger = logging.getLogger("voiceflow.startup")

_APP_NAME = "VoiceFlow"

if sys.platform == "win32":
    import winreg

    _RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _argv() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, "-m", "voiceflow.main"]


# ── Windows (HKCU Run) ─────────────────────────────────────────────────────────

def _win_command() -> str:
    return " ".join(f'"{a}"' for a in _argv())


def _win_enable() -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _win_command())


def _win_disable() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _APP_NAME)
    except FileNotFoundError:
        pass


def _win_is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, _APP_NAME)
        return True
    except FileNotFoundError:
        return False


# ── macOS (LaunchAgent) ────────────────────────────────────────────────────────

def _mac_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / "com.voiceflow.app.plist"


def _mac_enable() -> None:
    args = "".join(f"    <string>{a}</string>\n" for a in _argv())
    plist = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0"><dict>\n'
        '  <key>Label</key><string>com.voiceflow.app</string>\n'
        f'  <key>ProgramArguments</key><array>\n{args}  </array>\n'
        '  <key>RunAtLoad</key><true/>\n'
        '</dict></plist>\n'
    )
    p = _mac_plist_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(plist, encoding="utf-8")


def _mac_disable() -> None:
    _mac_plist_path().unlink(missing_ok=True)


def _mac_is_enabled() -> bool:
    return _mac_plist_path().exists()


# ── Linux (XDG autostart) ──────────────────────────────────────────────────────

def _linux_desktop_path() -> Path:
    return Path.home() / ".config" / "autostart" / "voiceflow.desktop"


def _linux_enable() -> None:
    exec_line = " ".join(_argv())
    entry = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=VoiceFlow\n"
        f"Exec={exec_line}\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    p = _linux_desktop_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(entry, encoding="utf-8")


def _linux_disable() -> None:
    _linux_desktop_path().unlink(missing_ok=True)


def _linux_is_enabled() -> bool:
    return _linux_desktop_path().exists()


# ── public API ─────────────────────────────────────────────────────────────────

def enable() -> None:
    if sys.platform == "win32":
        _win_enable()
    elif sys.platform == "darwin":
        _mac_enable()
    elif sys.platform.startswith("linux"):
        _linux_enable()
    else:
        return
    logger.info("Enabled start-on-login")


def disable() -> None:
    if sys.platform == "win32":
        _win_disable()
    elif sys.platform == "darwin":
        _mac_disable()
    elif sys.platform.startswith("linux"):
        _linux_disable()
    logger.info("Disabled start-on-login")


def is_enabled() -> bool:
    if sys.platform == "win32":
        return _win_is_enabled()
    if sys.platform == "darwin":
        return _mac_is_enabled()
    if sys.platform.startswith("linux"):
        return _linux_is_enabled()
    return False


def apply(enabled: bool) -> None:
    enable() if enabled else disable()
