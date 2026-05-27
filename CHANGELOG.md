# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-05-27

Initial public release.

### Added
- Voice-to-text: hold or double-tap **Left Ctrl + Left Alt** to record; audio is
  transcribed by the OpenAI API, filler words are stripped, and the cleaned text is
  pasted at the cursor.
- Desktop UI: main window with status + how-to, a recording/transcribing overlay,
  and silent auto-dismiss toasts (toggleable).
- System tray: Open, Settings, Retry Failed, Quit. Closing or minimizing the window
  keeps the app running in the tray.
- Settings dialog: OpenAI API key, model, notifications, and start-on-login.
- Start-on-login via a per-user registry entry.
- Disk-backed retry queue: failed transcriptions are retried automatically (max 3
  attempts) and can be retried manually from the tray.
- Standalone Windows packaging via PyInstaller + an Inno Setup installer.

### Privacy
- No transcript text is ever persisted; logs contain metadata only.
- Audio is deleted immediately after a successful paste, kept only on failure for
  retry.
- The API key is stored locally and sent only to OpenAI; no telemetry.

[Unreleased]: https://github.com/apgodlike/voiceflow/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/apgodlike/voiceflow/releases/tag/v0.1.0
