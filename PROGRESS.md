# VoiceFlow — Build Progress

Last completed step: 0

## Steps

- [x] Step 0: Scaffold — dirs, requirements.txt, .env.example, .gitignore, PLAN.md, git init
- [ ] Step 1: recorder.py — chunked WAV write (sounddevice + soundfile, 16kHz mono int16)
- [ ] Step 2: transcriber.py — OpenAI Whisper API call
- [ ] Step 3: cleaner.py — regex filler strip + text cleanup
- [ ] Step 4: paster.py — pyperclip copy + pyautogui Ctrl+V
- [ ] Step 5: queue.py — disk-backed JSON queue + sqlite history
- [ ] Step 6: hotkey.py — pynput hold/double-tap state machine
- [ ] Step 7: tray.py — pystray icon + dynamic menu
- [ ] Step 8: main.py — orchestration + 60s background sweeper

## Notes

### Step 0 (2026-05-14)
- Python 3.12.10
- Windows 11 Pro
- Created full dir tree: voiceflow/voiceflow/, voiceflow/tests/, voiceflow/data/recordings/, voiceflow/data/queue/
- venv created, requirements installed
