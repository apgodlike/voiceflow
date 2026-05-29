# Step 01 — Create Branch + Add Dependency

**Phase:** P1 (must complete before any other step)
**Depends on:** nothing

## Context

Working directory: `C:\dev\projects\voice-typing\voiceflow`
Branch to create: `feature/local-model`

`faster-whisper` is the CPU-optimized Whisper inference library (uses CTranslate2).
Version 1.1.1 is pinned for reproducibility.

## Task

### 1. Create the git branch

```powershell
cd C:\dev\projects\voice-typing\voiceflow
git checkout -b feature/local-model
```

### 2. Add dependency to requirements.txt

File: `C:\dev\projects\voice-typing\voiceflow\requirements.txt`

Current content (read before editing):
```
sounddevice==0.5.5
soundfile==0.13.1
numpy==2.4.4
openai==2.36.0
pynput==1.8.2
pyperclip==1.11.0
PyAutoGUI==0.9.54
pystray==0.19.5
Pillow==12.2.0
python-dotenv==1.2.2
```

Add `faster-whisper==1.1.1` as a new line at the end:
```
sounddevice==0.5.5
soundfile==0.13.1
numpy==2.4.4
openai==2.36.0
pynput==1.8.2
pyperclip==1.11.0
PyAutoGUI==0.9.54
pystray==0.19.5
Pillow==12.2.0
python-dotenv==1.2.2
faster-whisper==1.1.1
```

## Acceptance Criteria

- `git branch` shows `* feature/local-model`
- `requirements.txt` last line is `faster-whisper==1.1.1`
