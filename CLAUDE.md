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
python -m voiceflow.transcriber path/to/file.ogg  # needs OPENAI_API_KEY
```

## Architecture

The pipeline is strictly linear — each stage hands off to the next via `main.py`:

```
hotkey.py → recorder.py → queue.py → transcriber.py → cleaner.py → paster.py → queue.py (mark_success)
```

**Key design constraints:**

1. **Audio written to disk during recording** — `recorder.py` uses `soundfile.SoundFile` in write mode (OGG/Vorbis) and flushes each chunk in the `sounddevice` callback. Do not buffer audio in memory.

2. **Segmented fast-path with full-file fallback (latency)** — recorder writes the **full** continuous OGG (`{rid}.ogg`, the durable unit) *plus* rolling **segment** files (`{rid}.seg{n}.ogg`) cut on silence by `_SegmentCutter`. Each closed segment fires `on_segment`, so `main.py` transcribes segments concurrently *during* recording; on stop it stitches results in index order and pastes. If any segment transcription fails, it discards the partial and falls back to transcribing the full file via the queue path. Cuts land only inside silence gaps → no spoken word spans a boundary → plain concatenation, no overlap/dedup. The queue/retry/privacy model operates only on the full file; segments are ephemeral and always deleted after finalize.

3. **No retry logic in `transcriber.py`** — it raises `TranscriptionError` on any failure. Retries are owned entirely by `queue.py` + the sweeper in `main.py`. The module caches one `OpenAI` client (connection reuse); `reset_client()` drops it after a key/model change.

4. **Clipboard always set before paste** — `paster.paste()` calls `pyperclip.copy()` unconditionally before attempting `pyautogui.hotkey()`. If pyautogui fails, the function logs a warning and returns `False`; caller must not treat this as fatal.

5. **Queue files are atomic** — `queue.py` writes to `.tmp` then `os.replace()`. Never write queue JSON directly to the target path.

6. **No transcript persistence (privacy)** — `mark_success` deletes the audio file and the queue entry; nothing is stored. Audio survives only on failure, so a job can be retried. Segment temp files hold dictated audio too — they are deleted after every finalize (the full file is the retry source). Never log dictated content — logs carry metadata only.

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

`clean()` takes three optional config-driven kwargs (defaults reproduce the original zero-config behavior, so `clean(text)` is unchanged): `dictionary` (phrase→replacement map, applied first, longest-key-first, case-insensitive, target inserted verbatim via a lambda so `\1` in the value stays literal), `extra_fillers` (merged into the built-in filler regex), and `voice_commands` (opt-in, default off — spoken "comma"/"period"/"new line"/"new paragraph"/… become literal symbols; newlines round-trip through `\x00…\x00` sentinels that survive whitespace collapse and are restored last). `main.App._clean` passes the user's `config.json` values in; there is no Settings-GUI editor for these yet (users edit `config.json` directly).

## Tray

`tray.py` generates 16×16 solid-circle PNG icons inline via Pillow — no external image files. Icon color reflects state: gray=idle, red=recording, yellow=transcribing, orange=has-failed-jobs. The menu is rebuilt dynamically on each open via `pystray.Menu(self._build_menu)` (callable form).

## Data Paths

All data paths resolve through `paths.py` (single source of truth). Base dir is
`VOICEFLOW_DATA_DIR` → `%LOCALAPPDATA%\VoiceFlow` → `<repo>/data` fallback. Modules
import `paths` rather than computing `__file__`-relative paths. This keeps the app
working when installed to read-only Program Files and when frozen by PyInstaller.

## Environment

- `OPENAI_API_KEY` — required for transcription
- `VOICEFLOW_HOTKEY` — optional, default `ctrl+alt`
- `VOICEFLOW_MODEL` — optional, default `gpt-4o-mini-transcribe`
- `VOICEFLOW_DATA_DIR` — optional, overrides the data base dir
- `python-dotenv` loads `.env` in `main.py` at startup; other modules read from `os.environ` directly via the OpenAI SDK's default key lookup
