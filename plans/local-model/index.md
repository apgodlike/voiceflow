# Local Whisper Model Support — Feature Plan

## Goal

Add a local Whisper transcription backend via `faster-whisper` so users can run VoiceFlow
without an OpenAI API key, offline, at zero cost. A tray menu item toggles between
`openai` and `local` backends live (no restart needed).

## Architecture Decision

- `transcriber.py` stays unchanged (OpenAI backend).
- New `voiceflow/transcriber_local.py` — local backend, same `transcribe()` signature.
- `main.py` routes via `App._transcribe()` based on `cfg["backend"]`.
- CPU serialization: `_infer_lock` in transcriber_local prevents CPU thrash when the
  segment pipeline submits concurrent calls.
- `config.py` adds `"backend"` + `"local_model"` keys.
- `tray.py` adds a "Backend: X → toggle" menu item.

## Target hardware

Ryzen 5 5600G, no GPU. Recommended: `tiny` (~1s/segment) or `base` (~2.5s/segment).
`small` is marginal; `medium`+ too slow for real-time dictation.

## Parallel Execution Groups

| Phase | Step | Depends On | Can Parallel? |
|-------|------|------------|---------------|
| P1 | step-01-branch-deps | — | No |
| P2 | step-02-transcriber-local | step-01 | Yes (P2) |
| P2 | step-03-config | step-01 | Yes (P2) |
| P3 | step-04-routing | step-02, step-03 | No |
| P4 | step-05-tray-hotswap | step-04 | Yes (P4) |
| P4 | step-06-tests | step-04 | Yes (P4) |

## Files Changed

| File | Step | Action |
|------|------|--------|
| `requirements.txt` | 01 | add `faster-whisper==1.1.1` |
| `voiceflow/transcriber_local.py` | 02 | create new |
| `voiceflow/config.py` | 03 | edit DEFAULTS + validate() |
| `voiceflow/main.py` | 04, 05 | edit routing + tray wiring |
| `voiceflow/tray.py` | 05 | edit backend toggle menu |
| `tests/test_transcriber_local.py` | 06 | create new |

## Step Files

- [step-01-branch-deps.md](step-01-branch-deps.md)
- [step-02-transcriber-local.md](step-02-transcriber-local.md)
- [step-03-config.md](step-03-config.md)
- [step-04-routing.md](step-04-routing.md)
- [step-05-tray-hotswap.md](step-05-tray-hotswap.md)
- [step-06-tests.md](step-06-tests.md)

## Verification (after all steps complete)

```powershell
# 1. Smoke-test the local backend module
venv\Scripts\activate
pip install faster-whisper
python -m voiceflow.transcriber_local <path\to\any.ogg> --model base

# 2. Run with local backend
# Edit %LOCALAPPDATA%\VoiceFlow\config.json → set "backend": "local", "local_model": "base"
python -m voiceflow.main
# Dictate → see "Transcribing ... via local whisper-base" in logs

# 3. Tray toggle
# Right-click tray → click "Backend: local → toggle" → toast + switches to openai

# 4. Tests
pytest tests/test_transcriber_local.py -v

# 5. Full test suite
pytest
```
