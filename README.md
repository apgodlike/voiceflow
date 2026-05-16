# VoiceFlow

Windows desktop voice-to-text app. Hold or double-tap **Left Ctrl + Left Alt** → mic records → OpenAI Whisper transcribes → filler words stripped → cleaned text auto-pasted at cursor via clipboard + Ctrl+V.

## Quick Start

**Requirements:** Python 3.11+, Windows 11, OpenAI API key.

```powershell
cd voiceflow
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
# Edit .env — set OPENAI_API_KEY=sk-...

python -m voiceflow.main
```

Tray icon appears in system tray. Hold Ctrl+Alt to record.

## Hotkey

Two activation modes, both bound to **Left Ctrl + Left Alt**:

| Mode | Gesture | Behavior |
|------|---------|----------|
| **Hold** | Press and hold both keys | Recording starts after 200 ms debounce; release either key → stops |
| **Toggle** | Double-tap (both keys down+up+down+up within 400 ms) | Recording starts and stays on after keys released; next tap (single or double) stops |

> Override hotkey via `VOICEFLOW_HOTKEY=ctrl+alt` in `.env` (default is `ctrl+alt`).

## What Happens After You Record

```
mic audio
  │
  ▼  (16 kHz mono int16, chunked to disk during recording)
data/recordings/{uuid}.wav
  │
  ▼  (OpenAI Whisper API, 30 s timeout)
raw transcript
  │
  ▼  (regex filler strip)
cleaned text
  │
  ▼  (pyperclip.copy always runs first, then pyautogui Ctrl+V)
cursor
```

If Whisper fails → job saved to `data/queue/{uuid}.json` → background sweeper retries every 60 s, max 3 attempts. Manual retry available from tray menu.

## Filler Words Stripped

`uh`, `um`, `er`, `ah`, `you know`, `i mean`, `basically`, trailing `right`, leading `so`.

`like` is only stripped when preceded by a form of "to be" (e.g. "I was like going" → "I was going"). "I like coffee" is left unchanged.

## Tray Icon Colors

| Color | Meaning |
|-------|---------|
| Gray | Idle |
| Red | Recording |
| Yellow | Transcribing |
| Orange | Has failed jobs |

Tray menu: Status · History (last 10 transcriptions) · Retry Failed · Quit.

## Configuration

`.env` variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | — | OpenAI API key for Whisper |
| `VOICEFLOW_HOTKEY` | No | `ctrl+alt` | Hotkey combo |

## Data Layout

```
voiceflow/
└── data/
    ├── recordings/    WAV files (16 kHz mono int16)
    ├── queue/         Pending/failed jobs as {uuid}.json
    └── history.sqlite Successful transcription history
```

Queue JSON schema:
```json
{
  "recording_id": "hex-uuid",
  "wav_path": "data/recordings/....wav",
  "status": "pending|failed",
  "attempts": 0,
  "last_error": "",
  "created_at": "2026-05-14T..."
}
```

History table: `id`, `raw_text`, `cleaned_text`, `wav_path`, `created_at`.

## Module Reference

Each module is independently runnable via `python -m voiceflow.<module> --test`.

| Module | Purpose | CLI smoke test |
|--------|---------|----------------|
| `recorder.py` | Chunked WAV write via sounddevice + soundfile | Records 3 s, prints path + size |
| `transcriber.py` | OpenAI Whisper API call | `python -m voiceflow.transcriber path/to/file.wav` |
| `cleaner.py` | Regex filler strip + text normalization | `python -m voiceflow.cleaner "um so basically hello"` |
| `paster.py` | pyperclip copy + pyautogui Ctrl+V | Sleeps 3 s then pastes "hello world" |
| `queue.py` | Disk-backed JSON queue + sqlite history | `python -m voiceflow.queue --list` / `--retry-all` |
| `hotkey.py` | pynput hold/double-tap state machine | Prints START/STOP events interactively |
| `tray.py` | pystray icon + dynamic menu | Cycles icon states every 2 s |
| `main.py` | Orchestration + 60 s background sweeper | `python -m voiceflow.main` |

## Testing

```powershell
cd voiceflow
venv\Scripts\activate
pytest
```

37 tests across 5 modules (`test_recorder`, `test_transcriber`, `test_cleaner`, `test_paster`, `test_queue`, `test_hotkey`). All modules monkeypatched — no network calls, no mic access required.

Run a single module's tests:
```powershell
pytest tests/test_cleaner.py -v
```

## Architecture

```
keyboard ──── hotkey.py ─── on_start / on_stop callbacks
                  │
                  ▼
            recorder.py ──────────────── data/recordings/{uuid}.wav
                  │                              │
                  ▼                              │
            queue.py ◄─── enqueue ──────────────┘
                  │  (worker thread pulls job)
                  ▼
          transcriber.py ── OpenAI Whisper API
                  │
                  ▼
            cleaner.py ── regex filler strip
                  │
                  ▼
            paster.py ── pyperclip + pyautogui Ctrl+V
                  │
                  ▼  on success
            queue.py ── mark_success → history.sqlite

tray.py  runs on main thread, polls queue + recorder state for icon color
main.py  wires all modules + runs 60 s background retry sweeper
```

## Crash Recovery

Audio is written to disk **continuously during recording** via chunked `soundfile.SoundFile` writes. A crash mid-record leaves a usable (partial) WAV. On restart, `main.py` immediately sweeps `data/queue/` and retries any pending jobs (max 3 attempts each).

## Troubleshooting

**Paste doesn't work in some windows**
`pyautogui` can fail under UAC-elevated windows. The clipboard is always set via `pyperclip.copy` before the Ctrl+V attempt — paste manually with Ctrl+V if auto-paste fails.

**Hotkey not detected**
Some anti-cheat or accessibility tools intercept `pynput`. Try running VoiceFlow as administrator.

**`sounddevice` can't open mic**
Run `python -c "import sounddevice; print(sounddevice.query_devices())"` to list devices. Check Windows mic privacy settings (Settings → Privacy → Microphone).

**Whisper keeps failing**
Check `OPENAI_API_KEY` in `.env`. Failures land in `data/queue/` and are retried automatically every 60 s.

## Dependencies

```
sounddevice   # mic capture
soundfile     # chunked WAV write
numpy         # audio buffer dtype
openai        # Whisper API
pynput        # global hotkey listener
pyperclip     # clipboard
pyautogui     # Ctrl+V simulation
pystray       # Windows system tray
Pillow        # tray icon image generation
python-dotenv # .env loading
pytest        # tests
```
