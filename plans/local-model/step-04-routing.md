# Step 04 — Add Backend Routing in main.py

**Phase:** P3 (sequential — needs step-02 and step-03 done)
**Depends on:** step-02, step-03

## Context

Working directory: `C:\dev\projects\voice-typing\voiceflow`
Branch: `feature/local-model`
File to edit: `voiceflow/main.py`

The `App` class currently calls `transcriber.transcribe()` directly in two places:
- `_process_job` at line ~117
- `_on_segment` executor.submit at line ~177

We add `App._transcribe()` as a dispatcher that routes to either `transcriber.transcribe`
(OpenAI) or `transcriber_local.transcribe` (local) based on `cfg["backend"]`.

Also:
- When switching to openai backend, free local model RAM via `reset_model()`
- Suppress the first-run API key window when `backend == "local"` (no key needed)
- Toast user once when local model starts loading

## Task

Read `C:\dev\projects\voice-typing\voiceflow\voiceflow\main.py` in full before editing.

### Change 1 — `_has_key` in `__init__`

Current (around line 67):
```python
        _has_key = bool(self._cfg.get("openai_api_key", ""))
```

Replace with:
```python
        _has_key = (
            bool(self._cfg.get("openai_api_key", ""))
            or self._cfg.get("backend") == "local"
        )
```

### Change 2 — `_apply_config_env` method

Current method body ends with:
```python
        transcriber.reset_client()  # key/model may have changed — rebuild lazily
```

Add after that line:
```python
        if self._cfg.get("backend", "openai") == "openai":
            try:
                from voiceflow import transcriber_local
                transcriber_local.reset_model()
            except ImportError:
                pass
```

### Change 3 — add `_transcribe` method to `App`

Add this new method anywhere between `_apply_config_env` and `_on_settings_saved`
(i.e., in the config section of the class):

```python
    def _transcribe(self, audio_path: Path, language: str | None = None) -> str:
        """Dispatch transcription to openai or local backend per config."""
        backend = self._cfg.get("backend", "openai")
        if backend == "local":
            from voiceflow import transcriber_local
            model_name = self._cfg.get("local_model", "base")
            if not transcriber_local.is_loaded():
                self._ui.toast(f"Loading local Whisper model '{model_name}'…")
            return transcriber_local.transcribe(audio_path, language=language,
                                                model_name=model_name)
        return transcriber.transcribe(audio_path, language=language)
```

### Change 4 — `_process_job`: replace direct transcriber call

Current (around line 117):
```python
            raw = transcriber.transcribe(audio_path, language=self._cfg.get("language") or None)
```

Replace with:
```python
            raw = self._transcribe(audio_path, language=self._cfg.get("language") or None)
```

### Change 5 — `_on_segment`: replace executor.submit target

Current (around line 177):
```python
        fut = self._executor.submit(transcriber.transcribe, path, lang)
```

Replace with:
```python
        fut = self._executor.submit(self._transcribe, path, lang)
```

## Acceptance Criteria

- `python -c "from voiceflow.main import App"` imports without error
- No references to `transcriber.transcribe` remain inside `_process_job` or `_on_segment`
  (the import at the top of the file is fine to keep)
- `_transcribe` method exists on `App` class
