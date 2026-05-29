# Step 03 — Add Backend Config Keys to config.py

**Phase:** P2 (parallel with step-02)
**Depends on:** step-01 (branch must exist)

## Context

Working directory: `C:\dev\projects\voice-typing\voiceflow`
Branch: `feature/local-model`
File to edit: `voiceflow/config.py`

Two new config keys:
- `"backend"` — which transcription engine to use: `"openai"` or `"local"`
- `"local_model"` — which faster-whisper model: `"tiny"`, `"base"`, `"small"`, `"medium"`, `"large"`

## Task

### 1. Read the file first

Read `C:\dev\projects\voice-typing\voiceflow\voiceflow\config.py` in full before editing.

### 2. Add to DEFAULTS dict

The `DEFAULTS` dict currently ends with:
```python
    "paste_mode": "clipboard",  # "clipboard" (Ctrl+V) or "type" (character-by-character)
    "input_device": None,       # sounddevice input device index; None = system default
```

Add two new keys after `"input_device"`:
```python
    "backend": "openai",        # "openai" | "local" — transcription backend
    "local_model": "base",      # faster-whisper model: tiny, base, small, medium, large
```

### 3. Add validation in validate()

The `validate()` function currently ends with:
```python
    language = cfg.get("language", "")
    if language and not isinstance(language, str):
        warnings.append("'language' must be a string (ISO-639-1 code, e.g. \"en\") or empty string.")

    return warnings
```

Insert these two validation blocks before `return warnings`:
```python
    backend = cfg.get("backend", "openai")
    if backend not in ("openai", "local"):
        warnings.append(
            f"'backend' must be \"openai\" or \"local\"; got {backend!r}. Falling back to openai."
        )

    local_model = cfg.get("local_model", "base")
    if local_model not in ("tiny", "base", "small", "medium", "large"):
        warnings.append(
            f"'local_model' must be one of tiny/base/small/medium/large; got {local_model!r}."
        )
```

## Acceptance Criteria

- `python -c "from voiceflow import config; d = config.DEFAULTS; print(d['backend'], d['local_model'])"` prints `openai base`
- `python -c "from voiceflow import config; w = config.validate({'backend': 'bad', 'local_model': 'bad'}); print(len(w) >= 2)"` prints `True`
