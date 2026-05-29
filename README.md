# VoiceFlow

**Free, open-source alternative to Wispr Flow for Windows.**

Hold **Ctrl + Alt**, speak, release — cleaned text appears at your cursor instantly.
No subscription. No account. Bring your own OpenAI key.

<!-- DEMO GIF — record with ScreenToGif: hold Ctrl+Alt → speak → text appears -->
<!-- ![VoiceFlow demo](docs/images/demo.gif) -->

## Download

1. Grab **`VoiceFlow-Setup.exe`** from the [Releases page](https://github.com/apgodlike/voiceflow/releases).
2. Run it. Windows may warn "Windows protected your PC" (unsigned) — click **More info → Run anyway**.
3. On first launch the Settings window opens — paste your OpenAI API key. Need one? See [Getting an OpenAI API key](docs/getting-an-openai-api-key.md).

Hold **Ctrl + Alt** and talk. That's it.

## Features

| | VoiceFlow | Wispr Flow |
|---|---|---|
| Price | **Free** | $14/month |
| Source | **Open source (MIT)** | Closed |
| Platform | Windows | Mac + Windows |
| Transcription | OpenAI API (your key) | Proprietary |
| Offline mode | Planned | Paid tier |

**What it does:**
- **Instant transcription** — silence-aware segmentation transcribes audio *during* recording so results appear the moment you stop talking
- **Animated overlay** — audio-reactive waveform bars while recording; traveling wave while transcribing
- **Smart cleaning** — strips filler words, auto-capitalizes sentences, punctuation voice commands
- **Language hint** — tell it your language/accent for better accuracy
- **Paste or type** — Ctrl+V (default) or character-by-character for apps that block clipboard paste
- **Paste Previous** — re-paste the last transcription from the tray menu
- **Mic picker** — choose any input device, not just the system default
- **Privacy-first** — audio deleted after paste, no transcript storage, no telemetry

## Quick Start (from source)

**Requirements:** Python 3.11+, Windows 11, OpenAI API key.

```powershell
cd voiceflow
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m voiceflow.main
```

Set your API key in Settings on first launch (or add `OPENAI_API_KEY=sk-...` to a `.env` file).

## Hotkey

Both modes use **Left Ctrl + Left Alt**:

| Mode | Gesture | Behavior |
|------|---------|----------|
| **Hold** | Press and hold | Recording starts after 200 ms; release → stops |
| **Toggle** | Double-tap (two down+up cycles within 400 ms) | Recording stays on; next tap stops |

Recording auto-stops at 10 minutes (configurable). Toast notifies you to start again.

## Settings

Open the Settings dialog (tray → Settings or press **Settings…** in the main window).

| Tab | What you can configure |
|-----|----------------------|
| **API** | OpenAI API key, transcription model |
| **Recording** | Input device (mic picker), language hint |
| **Behavior** | Paste method (clipboard/type), voice commands, code mode, raw mode, preserve clipboard |
| **Text** | Extra fillers to strip, custom dictionary (spoken word → replacement) |

All settings are saved to `%LOCALAPPDATA%\VoiceFlow\config.json`.

## Text Cleaning

By default VoiceFlow:
- Strips filler words: `uh um er ah you know i mean basically`, trailing `right`, leading `so`
- Strips `like` only after a to-be verb ("I was like going" → "I was going"; "I like coffee" → unchanged)
- Capitalizes the first letter and each sentence start
- Appends a period if the text has no terminal punctuation

**Opt-in modes** (set in Settings → Behavior or edit `config.json`):

| Mode | Effect |
|------|--------|
| `voice_commands` | "comma" / "period" / "new line" / "new paragraph" → literal symbols |
| `code_mode` | No auto-capitalize, no trailing period |
| `raw_mode` | Verbatim transcript — bypass all cleaning |

**Custom dictionary** (Settings → Text):
```json
{ "cloud": "Claude", "open ai": "OpenAI" }
```
Longest match wins, case-insensitive, replacement inserted verbatim.

## Privacy

- **No transcript storage.** Text is pasted and forgotten.
- **Audio lifecycle:** recorded to `%LOCALAPPDATA%\VoiceFlow\recordings\` → transcribed → deleted. Kept only if transcription fails (for retry), then deleted after max attempts.
- **Logs:** `voiceflow.log` — timing and file counts only, never transcript content.
- **No telemetry.** The app makes exactly one outbound call: audio → OpenAI transcription API. Nothing else.
- **API key** stored locally in `config.json`, never leaves your machine except in the OpenAI API header.

## Tray Icon

| Color | State |
|-------|-------|
| Gray | Idle |
| Red | Recording |
| Yellow | Transcribing |
| Orange | Failed jobs waiting for retry |

Right-click for: Open · Paste Previous · Settings · Retry Failed · Quit.

## Configuration Reference

`%LOCALAPPDATA%\VoiceFlow\config.json` — edit directly or use Settings:

| Key | Default | Description |
|-----|---------|-------------|
| `openai_api_key` | `""` | API key (fallback: `OPENAI_API_KEY` env var) |
| `model` | `gpt-4o-mini-transcribe` | Transcription model |
| `language` | `""` | ISO-639-1 hint, e.g. `"en"`, `"hi"` — blank = auto |
| `paste_mode` | `"clipboard"` | `"clipboard"` or `"type"` |
| `preserve_clipboard` | `false` | Restore prior clipboard after paste |
| `max_recording_sec` | `600` | Auto-stop cap in seconds; `0` = no cap |
| `voice_commands` | `false` | Spoken punctuation commands |
| `code_mode` | `false` | No auto-cap / no trailing period |
| `raw_mode` | `false` | Verbatim transcript |
| `dictionary` | `{}` | `{"spoken": "Replacement"}` map |
| `extra_fillers` | `[]` | Extra words to strip |
| `input_device` | `null` | Device index from `sounddevice.query_devices()` |
| `notifications_enabled` | `true` | Show paste toasts |
| `start_on_login` | `true` | Launch at Windows sign-in |
| `hotkey` | `"ctrl+alt"` | Hotkey combo |

Environment variables (`OPENAI_API_KEY`, `VOICEFLOW_MODEL`, `VOICEFLOW_DATA_DIR`) still work as overrides.

## Building from Source

```powershell
cd voiceflow
venv\Scripts\activate
pip install -r requirements-dev.txt

# Regenerate icon (optional)
python tools\make_icon.py

# Build onedir app
pyinstaller VoiceFlow.spec --noconfirm
# → dist\VoiceFlow\VoiceFlow.exe  (double-click to run)

# Wrap as installer (requires Inno Setup)
ISCC installer.iss
# → dist\VoiceFlow-Setup.exe
```

> **Always test on a machine without Python.** Missing native DLLs (PortAudio, libsndfile) only surface on a clean machine.

## Architecture

```
hotkey.py ──── on_start / on_stop
                    │
                    ▼
             recorder.py ─── silence-aware segments ──► transcriber.py (concurrent)
                    │                                          │ stitch on stop
                    │ full OGG (durable)                       ▼
                    ▼                                    cleaner.py
              queue.py ◄── enqueue ◄── fallback ◄──────      │
                    │  (sweeper retries on failure)           ▼
                    └──────────────────────────────►  paster.py ──► cursor
```

- **Segments transcribed concurrently during recording** → no waiting at stop
- Full OGG is the durable retry/privacy unit; segments are ephemeral, always deleted
- Queue writes are atomic (`os.replace`); crash-safe

## Testing

```powershell
pytest
```

69 tests across config, cleaner, queue, transcriber, paster, recorder, hotkey.
All modules monkeypatched — no network, no mic required.

## Troubleshooting

**"Failed to execute script" or "python312.dll not found"**
You ran `VoiceFlow.exe` directly from inside a ZIP file. Windows only extracts the single EXE, leaving the required `_internal\` folder behind.
Fix: right-click the ZIP → **Extract All** → run `VoiceFlow.exe` from the extracted folder. Or use the installer (`VoiceFlow-Setup.exe`) which handles this automatically.

**Paste doesn't land** — `pyautogui` can fail under UAC-elevated windows. Text is always in the clipboard; paste manually with Ctrl+V. Or switch to `paste_mode: "type"` in Settings.

**Hotkey not detected** — some anti-cheat / accessibility tools intercept `pynput`. Try running as administrator.

**Mic not opening** — check Windows Settings → Privacy → Microphone. List devices: `python -c "import sounddevice; print(sounddevice.query_devices())"`.

**Transcription keeps failing** — check your API key in Settings. Failed jobs are retried automatically every 60 s and show as an orange tray icon.

**SmartScreen warning on install** — app is unsigned. Click **More info → Run anyway**. Source is fully auditable above.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome.

## License

MIT — see [LICENSE](LICENSE). Free to use, modify, and distribute.
