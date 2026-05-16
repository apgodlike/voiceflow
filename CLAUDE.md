# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands run from the `voiceflow/` directory with venv active:

```powershell
venv\Scripts\activate
```

**Run all tests:**
```powershell
pytest
```

**Run a single test file:**
```powershell
pytest tests/test_cleaner.py -v
```

**Run the app:**
```powershell
python -m voiceflow.main
```

**Smoke-test a single module (no mic/API needed except transcriber):**
```powershell
python -m voiceflow.recorder --test
python -m voiceflow.cleaner "um so basically hello world right"
python -m voiceflow.paster "hello world"       # sleeps 3 s then pastes
python -m voiceflow.queue --list
python -m voiceflow.hotkey --test              # interactive, Ctrl+C to exit
python -m voiceflow.tray --test               # cycles icon states
python -m voiceflow.transcriber path/to/file.wav  # needs OPENAI_API_KEY
```

## Architecture

The pipeline is strictly linear — each stage hands off to the next via `main.py`:

```
hotkey.py → recorder.py → queue.py → transcriber.py → cleaner.py → paster.py → queue.py (mark_success)
```

**Key design constraints:**

1. **Audio written to disk during recording** — `recorder.py` uses `soundfile.SoundFile` in write mode and flushes each chunk in the `sounddevice` callback. Whisper is called only after `stop_recording()` closes the file. Do not buffer audio in memory.

2. **No retry logic in `transcriber.py`** — it raises `TranscriptionError` on any failure. Retries are owned entirely by `queue.py` + the sweeper in `main.py`.

3. **Clipboard always set before paste** — `paster.paste()` calls `pyperclip.copy()` unconditionally before attempting `pyautogui.hotkey()`. If pyautogui fails, the function logs a warning and returns `False`; caller must not treat this as fatal.

4. **Queue files are atomic** — `queue.py` writes to `.tmp` then `os.replace()`. Never write queue JSON directly to the target path.

5. **SQLite is opened per-call** — each `mark_success` opens and closes its own connection to avoid `check_same_thread` issues across the executor threads.

## Hotkey State Machine

`hotkey.py` separates `_StateMachine` (pure logic, no pynput) from `HotkeyController` (wraps pynput listener). Tests drive `_StateMachine` directly by calling `key_press` / `key_release` with pynput Key objects.

States: `IDLE → RECORDING_HOLD → IDLE` (hold path) or `IDLE → RECORDING_TOGGLE → IDLE` (double-tap path).

- Hold fires after `HOLD_DEBOUNCE_MS = 200` ms via a `threading.Timer`. Quick release before 200 ms cancels the timer — no start fires.
- Double-tap: second "both-down" within `DOUBLE_TAP_WINDOW_MS = 400` ms of the previous "either-up" triggers toggle. `_last_release_time` tracks this.
- In `RECORDING_TOGGLE`, any "both-down" event stops recording (both single-tap and double-tap stop).

## Cleaner Regex Order Matters

`cleaner.py` applies passes in order — order is not interchangeable:
1. Strip simple fillers (`uh`, `um`, `er`, `ah`, `you know`, `i mean`, `basically`)
2. Strip trailing `right` (before punctuation or EOL)
3. Strip `<be-verb> like` (not bare `like`)
4. Collapse whitespace, strip leading `so`, strip leading punctuation
5. Capitalize first char, append `.` if no terminal punctuation

`like` is only stripped when preceded by a "to be" verb (`was/am/were/is/are/been/being/be`). The regex captures the verb in group 1 and substitutes back `\1` to preserve the verb.

## Tray

`tray.py` generates 16×16 solid-circle PNG icons inline via Pillow — no external image files. Icon color reflects state: gray=idle, red=recording, yellow=transcribing, orange=has-failed-jobs. The menu is rebuilt dynamically on each open via `pystray.Menu(self._build_menu)` (callable form).

## Data Paths

All data paths are relative to `voiceflow/data/` (resolved from `__file__` in each module — not from cwd). Running modules from any working directory works correctly.

## Environment

- `OPENAI_API_KEY` — required for transcription
- `VOICEFLOW_HOTKEY` — optional, default `ctrl+alt`
- `python-dotenv` loads `.env` in `main.py` at startup; other modules read from `os.environ` directly via the OpenAI SDK's default key lookup
