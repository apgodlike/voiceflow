"""User configuration — persisted as JSON in the data dir.

The API key and model live here so non-technical users can set them from the
Settings dialog instead of editing a ``.env`` file. Environment variables still
win as a fallback so the developer ``.env`` workflow keeps working.
"""
import json
import logging
import os
from typing import Any

from voiceflow import paths

logger = logging.getLogger("voiceflow.config")

DEFAULTS: dict[str, Any] = {
    "openai_api_key": "",
    "hotkey": "ctrl+alt",
    "model": "gpt-4o-mini-transcribe",
    "notifications_enabled": True,
    "start_on_login": True,
    "dictionary": {},          # {"spoken": "Replacement"} — fix mistranscribed terms
    "extra_fillers": [],       # extra words to strip alongside built-in fillers
    "voice_commands": False,   # opt-in: "comma"/"new line"/… → literal punctuation
    "code_mode": False,        # skip auto-capitalize + auto-period (dictating code)
    "raw_mode": False,         # deliver verbatim transcript, bypass the cleaner
    "preserve_clipboard": False,  # restore prior clipboard after paste (verify timing)
    "max_recording_sec": 600,  # auto-stop a runaway recording at 10 min (0 = no cap)
}


def load() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    try:
        if paths.CONFIG_PATH.exists():
            cfg.update(json.loads(paths.CONFIG_PATH.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read config (%s); using defaults", exc)
    return cfg


def save(cfg: dict[str, Any]) -> None:
    paths.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    os.replace(tmp, paths.CONFIG_PATH)


def resolved_api_key(cfg: dict[str, Any]) -> str:
    """Config value wins; fall back to the environment (dev ``.env``)."""
    return cfg.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")


def resolved_model(cfg: dict[str, Any]) -> str:
    return cfg.get("model") or os.environ.get("VOICEFLOW_MODEL") or DEFAULTS["model"]
