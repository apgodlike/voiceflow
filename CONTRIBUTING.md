# Contributing to VoiceFlow

Thanks for your interest! VoiceFlow is a private, offline voice-to-text app —
Windows-first, with macOS/Linux via pipx. Contributions of all sizes are welcome.

## Dev setup

```powershell
git clone https://github.com/apgodlike/voiceflow.git
cd voiceflow
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt
```

No setup is needed for local mode (Parakeet/Whisper, the default — the first-run
wizard downloads a model). Only if you want **cloud** mode, set an OpenAI key in the
in-app Settings dialog or a `.env` file (`OPENAI_API_KEY=sk-...`).

## Run the app

```powershell
python -m voiceflow.main
```

## Tests

```powershell
pytest
```

All tests are offline — mic, network, and registry are monkeypatched, so the suite
runs without an API key or a microphone. Please add tests for new behavior and keep
the suite green.

Individual modules also have a smoke test:

```powershell
python -m voiceflow.recorder --test
python -m voiceflow.cleaner "um so basically hello"
python -m voiceflow.queue --list
```

## Building the installer

See the "Building from source" section in [README.md](README.md).
Always test the built `dist\VoiceFlow\VoiceFlow.exe` on a machine without Python.

## Conventions

- Python 3.11+, standard library `tkinter` for UI (no heavy GUI deps).
- All file paths go through `voiceflow/paths.py` — do not compute `__file__`-relative
  paths in other modules.
- Never log or persist dictated text (see [SECURITY.md](SECURITY.md)).
- Keep `transcriber.py` free of retry logic — retries belong to `queue.py` + the
  sweeper in `main.py`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `refactor:`, `docs:`, ...).

## Pull requests

1. Branch from `main`.
2. Keep changes focused; update `CHANGELOG.md` under "Unreleased".
3. Ensure `pytest` passes.
4. Open the PR with a clear description of what and why.
