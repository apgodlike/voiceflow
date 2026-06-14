# VoiceFlow — Build Progress

> **Historical build log** of the original v0.1 MVP (dated 2026-05-14). The project
> has evolved well past this — see [CHANGELOG.md](CHANGELOG.md) for what's shipped.
> Kept for provenance.

Last completed step: 8

## Steps

- [x] Step 0: Scaffold — dirs, requirements.txt, .env.example, .gitignore, PLAN.md, git init
- [x] Step 1: recorder.py — chunked WAV write (sounddevice + soundfile, 16kHz mono int16)
- [x] Step 2: transcriber.py — OpenAI Whisper API call
- [x] Step 3: cleaner.py — regex filler strip + text cleanup
- [x] Step 4: paster.py — pyperclip copy + pyautogui Ctrl+V
- [x] Step 5: queue.py — disk-backed JSON queue + sqlite history
- [x] Step 6: hotkey.py — pynput hold/double-tap state machine
- [x] Step 7: tray.py — pystray icon + dynamic menu
- [x] Step 8: main.py — orchestration + 60s background sweeper

## Notes

### Step 0 (2026-05-14)
- Python 3.12.10, Windows 11 Pro
- Created full dir tree

### Steps 1-8 (2026-05-14)
- 37 tests pass across 5 modules
- All modules independently runnable via `python -m voiceflow.<module> --test`
- `like` stripping narrowed to "to-be + like" form to avoid stripping verb uses
- Lookbehind variable-width regex issue fixed by using _BE_LIKE substitution approach
- pytest.ini added with `pythonpath = .` for package resolution
