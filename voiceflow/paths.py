"""Central data paths — single source of truth for where VoiceFlow writes.

Resolution order:
1. ``VOICEFLOW_DATA_DIR`` env var (tests / power users).
2. ``%LOCALAPPDATA%\\VoiceFlow`` on Windows — writable without admin, survives
   install to read-only Program Files, and avoids the PyInstaller one-dir temp
   path problem.
3. ``<repo>/data`` fallback for non-Windows dev / CI where LOCALAPPDATA is unset.
"""
import os
import sys
from pathlib import Path

_APP_NAME = "VoiceFlow"


def asset_path(name: str) -> Path:
    """Resolve a bundled asset in dev and in a PyInstaller bundle."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / "assets" / name


def _base_dir() -> Path:
    override = os.environ.get("VOICEFLOW_DATA_DIR")
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / _APP_NAME
    return Path(__file__).resolve().parent.parent / "data"


BASE_DIR = _base_dir()
RECORDINGS_DIR = BASE_DIR / "recordings"
QUEUE_DIR = BASE_DIR / "queue"
CONFIG_PATH = BASE_DIR / "config.json"
LOG_PATH = BASE_DIR / "voiceflow.log"
