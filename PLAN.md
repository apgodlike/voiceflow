# VoiceFlow MVP — Implementation Plan

## Context

Build **VoiceFlow**: a Windows desktop voice-to-text app. Hold-or-toggle hotkey → mic captures audio → audio written to disk continuously → OpenAI Whisper transcribes → regex filler-cleaner strips um/uh/etc. → cleaned text auto-pasted at cursor via clipboard + `Ctrl+V`.

## Hotkey Behavior

Two activation modes, both bound to **Left Ctrl + Left Alt**:

1. **Hold mode** — press and hold both keys → recording starts after 200 ms debounce → release either key → recording stops.
2. **Toggle mode** — **double-tap** (both keys down + up + down + up within 400 ms) → recording starts and stays on after keys released → **single tap or double tap** → recording stops.

State machine:
- `IDLE` → keys held >200ms → `RECORDING_HOLD` → release → fire `stop` → `IDLE`
- `IDLE` → second down within 400ms of first up → `RECORDING_TOGGLE` → fire `start`. Next tap in `RECORDING_TOGGLE` → fire `stop` → `IDLE`

## Stack

- Audio: `sounddevice` + `soundfile` (16 kHz mono int16)
- Whisper: `openai` SDK, model `whisper-1`, 30 s timeout
- Hotkey: `pynput` — hold-mode (>200 ms) OR double-tap-toggle (within 400 ms)
- Tray: `pystray` + `Pillow`
- Paste: `pyperclip` + `pyautogui`
- Queue: JSON files + sqlite (`data/history.sqlite`)

## Build Order

- Step 0: Scaffold (dirs, requirements.txt, .env.example, .gitignore, PLAN.md, PROGRESS.md, git init)
- Step 1: `recorder.py` — chunked WAV write via sounddevice + soundfile
- Step 2: `transcriber.py` — OpenAI Whisper API
- Step 3: `cleaner.py` — regex filler strip
- Step 4: `paster.py` — pyperclip + pyautogui
- Step 5: `queue.py` — disk-backed retry queue + sqlite history
- Step 6: `hotkey.py` — pynput state machine
- Step 7: `tray.py` — pystray icon + menu
- Step 8: `main.py` — orchestration + background sweeper

## Architecture

```
keyboard ── hotkey.py ── start/stop callbacks
                │
                ▼
         recorder.py ──── data/recordings/{uuid}.wav
                │
                ▼
         queue.py ◄── enqueue
                │
                ▼
         transcriber.py ── OpenAI Whisper
                │
                ▼
         cleaner.py ── regex filler strip
                │
                ▼
         paster.py ── pyperclip + pyautogui Ctrl+V
                │
                ▼ on success
         queue.py ── mark_success → history.sqlite

tray.py runs on main thread, polls queue + recorder state.
main.py wires it all together + runs 60s background retry sweeper.
```
