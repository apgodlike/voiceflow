# VoiceFlow

Windows desktop voice-to-text app. Hold or double-tap **Left Ctrl + Left Alt** → mic records → OpenAI transcription → filler words stripped → cleaned text auto-pasted at cursor via clipboard + Ctrl+V.

## Download (for users)

1. Grab the latest **`VoiceFlow-Setup.exe`** from the
   [Releases page](https://github.com/apgodlike/voiceflow/releases).
2. Run it. Windows may show "Windows protected your PC" (the app is unsigned) —
   click **More info → Run anyway**.
3. On first launch, paste your OpenAI API key in Settings. Need one? See
   [Getting an OpenAI API key](docs/getting-an-openai-api-key.md).

That's it — hold **Ctrl + Alt** and talk. Want to run from source instead? See below.

## Quick Start (from source)

**Requirements:** Python 3.11+, Windows 11, OpenAI API key.

```powershell
cd voiceflow
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

python -m voiceflow.main
```

On first launch the **Settings** window opens — paste your OpenAI API key and
save. A tray icon also appears. Hold Ctrl+Alt to record.

> Developers can instead set `OPENAI_API_KEY` in a `.env` file (copy
> `.env.example`); the env var is used as a fallback when no key is saved in Settings.

### Window & tray

- **Main window** shows status + how-to. Closing or minimizing it keeps VoiceFlow
  running in the tray — it does not quit.
- **Tray menu** (right-click): Open VoiceFlow · Settings · Retry Failed · Quit.
  **Quit** is the only way to fully stop the app.
- A small **overlay** appears while recording / transcribing, and a silent toast
  confirms each paste (toggle off in Settings).
- **Start on login** checkbox (default on) registers VoiceFlow to launch at sign-in.

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
  ▼  (16 kHz mono OGG/Vorbis, chunked to disk during recording)
recordings/{uuid}.ogg
  │
  ▼  (OpenAI transcription API, 30 s timeout)
raw transcript
  │
  ▼  (regex filler strip)
cleaned text
  │
  ▼  (pyperclip.copy always runs first, then pyautogui Ctrl+V)
cursor
```

On success the audio file is deleted immediately — no transcript is stored. If transcription fails → job saved to `queue/{uuid}.json` and the audio is kept → background sweeper retries every 60 s, max 3 attempts. Manual retry available from the tray menu.

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
| `OPENAI_API_KEY` | Yes | — | OpenAI API key for transcription |
| `VOICEFLOW_HOTKEY` | No | `ctrl+alt` | Hotkey combo |
| `VOICEFLOW_MODEL` | No | `gpt-4o-mini-transcribe` | Transcription model. Set to `gpt-4o-transcribe` for higher accuracy at ~2× cost |
| `VOICEFLOW_DATA_DIR` | No | `%LOCALAPPDATA%\VoiceFlow` | Override where recordings/queue/logs are written |

## Data Layout

All data lives under `%LOCALAPPDATA%\VoiceFlow\` (override with `VOICEFLOW_DATA_DIR`):

```
%LOCALAPPDATA%\VoiceFlow\
├── recordings/     OGG/Vorbis audio (16 kHz mono), deleted after a successful paste
├── queue/          Pending/failed jobs as {uuid}.json
└── voiceflow.log   Rotating log — metadata only, never transcript content
```

**Privacy:** no transcript text is ever persisted. Audio is kept only long enough
to transcribe and paste, then deleted; it survives only when a job fails, so it can
be retried. Logs record timing/counts, never what you dictated.

Queue JSON schema:
```json
{
  "recording_id": "hex-uuid",
  "audio_path": "...\\recordings\\....ogg",
  "status": "pending|failed",
  "attempts": 0,
  "last_error": "",
  "created_at": "2026-05-14T..."
}
```

## Module Reference

Each module is independently runnable via `python -m voiceflow.<module> --test`.

| Module | Purpose | CLI smoke test |
|--------|---------|----------------|
| `recorder.py` | Chunked OGG/Vorbis write via sounddevice + soundfile | Records 3 s, prints path + size |
| `transcriber.py` | OpenAI transcription API call | `python -m voiceflow.transcriber path/to/file.ogg` |
| `cleaner.py` | Regex filler strip + text normalization | `python -m voiceflow.cleaner "um so basically hello"` |
| `paster.py` | pyperclip copy + pyautogui Ctrl+V | Sleeps 3 s then pastes "hello world" |
| `queue.py` | Disk-backed JSON retry queue | `python -m voiceflow.queue --list` / `--retry-all` |
| `paths.py` | Central data-dir resolution (`%LOCALAPPDATA%`) | — |
| `hotkey.py` | pynput hold/double-tap state machine | Prints START/STOP events interactively |
| `tray.py` | pystray icon + dynamic menu | Cycles icon states every 2 s |
| `main.py` | Orchestration + 60 s background sweeper | `python -m voiceflow.main` |

## Testing

```powershell
cd voiceflow
venv\Scripts\activate
pytest
```

37 tests across 6 modules (`test_recorder`, `test_transcriber`, `test_cleaner`, `test_paster`, `test_queue`, `test_hotkey`). All modules monkeypatched — no network calls, no mic access required.

Run a single module's tests:
```powershell
pytest tests/test_cleaner.py -v
```

## Building the Windows installer

Produces a standalone app that needs no Python on the target machine.

```powershell
cd voiceflow
venv\Scripts\activate
pip install -r requirements-dev.txt

python tools\make_icon.py            # regenerate assets\icon.ico (optional)
pyinstaller VoiceFlow.spec --noconfirm   # → dist\VoiceFlow\VoiceFlow.exe (onedir)
```

The PyInstaller build bundles the PortAudio and libsndfile native DLLs explicitly
(they are not plain Python imports). **Always test `dist\VoiceFlow\VoiceFlow.exe`
on a machine with no Python installed** — a missing native DLL only shows up there.

To wrap it as `VoiceFlow-Setup.exe`, install [Inno Setup](https://jrsoftware.org/isdl.php)
and compile `installer.iss` (open in the IDE and press F9, or run `ISCC installer.iss`).
The installer does a per-user install (no admin), adds a Start Menu shortcut, an
optional "start on login" entry, and launches the app on finish.

> Unsigned builds trigger a Windows SmartScreen warning ("Windows protected your
> PC"). Click **More info → Run anyway**. Code signing would remove this.

## Architecture

```
keyboard ──── hotkey.py ─── on_start / on_stop callbacks
                  │
                  ▼
            recorder.py ──────────────── recordings/{uuid}.ogg
                  │                              │
                  ▼                              │
            queue.py ◄─── enqueue ──────────────┘
                  │  (worker thread pulls job)
                  ▼
          transcriber.py ── OpenAI transcription API
                  │
                  ▼
            cleaner.py ── regex filler strip
                  │
                  ▼
            paster.py ── pyperclip + pyautogui Ctrl+V
                  │
                  ▼  on success
            queue.py ── mark_success → delete audio + queue entry

main.py    App class wires all modules + runs 60 s background retry sweeper
tray.py    pystray icon (detached thread), reflects recorder/queue state
```

## Crash Recovery

Audio is written to disk **continuously during recording** via chunked `soundfile.SoundFile` writes. A crash mid-record leaves a usable (partial) OGG. On restart, `main.py` immediately sweeps the queue dir and retries any pending jobs (max 3 attempts each).

## Troubleshooting

**Paste doesn't work in some windows**
`pyautogui` can fail under UAC-elevated windows. The clipboard is always set via `pyperclip.copy` before the Ctrl+V attempt — paste manually with Ctrl+V if auto-paste fails.

**Hotkey not detected**
Some anti-cheat or accessibility tools intercept `pynput`. Try running VoiceFlow as administrator.

**`sounddevice` can't open mic**
Run `python -c "import sounddevice; print(sounddevice.query_devices())"` to list devices. Check Windows mic privacy settings (Settings → Privacy → Microphone).

**Transcription keeps failing**
Check `OPENAI_API_KEY` in `.env`. Failures land in the queue dir and are retried automatically every 60 s.

## Dependencies

```
sounddevice   # mic capture
soundfile     # chunked WAV write
numpy         # audio buffer dtype
openai        # transcription API
pynput        # global hotkey listener
pyperclip     # clipboard
pyautogui     # Ctrl+V simulation
pystray       # Windows system tray
Pillow        # tray icon image generation
python-dotenv # .env loading
pytest        # tests
```

## License

MIT — see [LICENSE](LICENSE). Free to use, modify, and distribute.
