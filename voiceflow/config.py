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
    "max_recording_sec": 1800,  # auto-stop a runaway recording at 30 min (0 = no cap)
    "language": "",             # ISO-639-1 hint for transcription (e.g. "en", "hi"); empty = auto
    "paste_mode": "clipboard",  # "clipboard" (Ctrl+V) or "type" (character-by-character)
    "input_device": None,       # sounddevice input device index; None = system default
    "backend": "openai",        # "openai" | "local" — transcription backend
    "local_model": "parakeet",  # local engine: "parakeet" (onnx) or a faster-whisper model
    "ai_cleanup": False,        # opt-in: run transcript through an LLM to fix grammar/format
    "ai_cleanup_provider": "ollama",  # "ollama" (local) | "openai" (cloud)
    "ai_cleanup_model": "",     # provider model; blank = provider default
    "ai_cleanup_prompt": "",    # custom prompt ({text} placeholder); blank = built-in
}


def load() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    try:
        if paths.CONFIG_PATH.exists():
            cfg.update(json.loads(paths.CONFIG_PATH.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read config (%s); using defaults", exc)
    for warning in validate(cfg):
        logger.warning("Config warning: %s", warning)
    return cfg


def save(cfg: dict[str, Any]) -> None:
    paths.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = paths.CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    os.replace(tmp, paths.CONFIG_PATH)


def validate(cfg: dict[str, Any]) -> list[str]:
    """Return a list of human-readable warnings for bad config values.

    Callers decide what to do (log, toast, etc.); this fn never raises.
    """
    warnings: list[str] = []

    dictionary = cfg.get("dictionary", {})
    if not isinstance(dictionary, dict):
        warnings.append("'dictionary' must be a JSON object {\"spoken\": \"Replacement\"}; ignoring.")
    else:
        for k, v in dictionary.items():
            if not isinstance(k, str) or not isinstance(v, str):
                warnings.append(
                    f"'dictionary' entry {k!r}: both key and value must be strings; ignoring entry."
                )

    extra_fillers = cfg.get("extra_fillers", [])
    if not isinstance(extra_fillers, list):
        warnings.append("'extra_fillers' must be a JSON array of strings; ignoring.")
    else:
        for item in extra_fillers:
            if not isinstance(item, str):
                warnings.append(
                    f"'extra_fillers' contains non-string item {item!r}; ignoring entry."
                )

    max_sec = cfg.get("max_recording_sec", 600)
    if not isinstance(max_sec, (int, float)):
        warnings.append("'max_recording_sec' must be a number (seconds, 0 to disable); ignoring.")
    elif max_sec < 0:
        warnings.append(f"'max_recording_sec' is {max_sec}; must be ≥ 0 (use 0 to disable cap).")

    model = cfg.get("model", "")
    if model and not isinstance(model, str):
        warnings.append("'model' must be a string; falling back to default.")

    hotkey = cfg.get("hotkey", "")
    if hotkey and not isinstance(hotkey, str):
        warnings.append("'hotkey' must be a string (e.g. \"ctrl+alt\"); falling back to default.")

    paste_mode = cfg.get("paste_mode", "clipboard")
    if paste_mode not in ("clipboard", "type"):
        warnings.append(
            f"'paste_mode' must be \"clipboard\" or \"type\"; got {paste_mode!r}. Falling back to clipboard."
        )

    language = cfg.get("language", "")
    if language and not isinstance(language, str):
        warnings.append("'language' must be a string (ISO-639-1 code, e.g. \"en\") or empty string.")

    backend = cfg.get("backend", "openai")
    if backend not in ("openai", "local"):
        warnings.append(
            f"'backend' must be \"openai\" or \"local\"; got {backend!r}. Falling back to openai."
        )

    local_model = cfg.get("local_model", "parakeet")
    _valid_models = (
        "parakeet",
        "tiny", "tiny.en", "base", "base.en", "small", "small.en",
        "distil-small.en", "medium", "medium.en", "distil-medium.en",
        "large", "distil-large-v3",
    )
    if local_model not in _valid_models:
        warnings.append(
            f"'local_model' must be one of {'/'.join(_valid_models)}; got {local_model!r}."
        )

    provider = cfg.get("ai_cleanup_provider", "ollama")
    if provider not in ("ollama", "openai"):
        warnings.append(
            f"'ai_cleanup_provider' must be \"ollama\" or \"openai\"; got {provider!r}."
        )

    return warnings


def resolved_api_key(cfg: dict[str, Any]) -> str:
    """Config value wins; fall back to the environment (dev ``.env``)."""
    return cfg.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")


def resolved_model(cfg: dict[str, Any]) -> str:
    return cfg.get("model") or os.environ.get("VOICEFLOW_MODEL") or DEFAULTS["model"]
