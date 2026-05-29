# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.3] - 2026-05-29

### Fixed
- Double-paste bug: the segment fast-path fallback in `_finalize_job` used an
  overbroad `try/except` that wrapped the paste itself. If `q.mark_success()` or
  `_on_paste_success()` raised after a successful paste, the `except` block
  triggered `_process_job()`, which transcribed and pasted again. The fallback
  now only catches segment `.result()` failures.
- Race condition in `_on_stop`: the max-duration timer thread and the hotkey
  thread could both read `_current_rid` as non-None before either set it to
  `None`, leading to two concurrent `_finalize_job` threads. A `_stop_lock`
  makes the read-check-clear of `_current_rid` atomic.

## [0.1.2] - 2026-05-29

### Fixed
- First-run window disappeared immediately on machines where `OPENAI_API_KEY`
  was set as a system/user environment variable (e.g. from a prior Python or
  OpenAI SDK install). First-run detection now checks only the VoiceFlow
  config file, not environment variables.
- Eliminated 1-frame white flash when starting in tray-only mode — window is
  now withdrawn before any widgets are drawn.

## [0.1.1] - 2026-05-29

### Fixed
- Sweeper race condition: `retry_all()` was picking up in-flight jobs (status=pending),
  causing two threads to open the same audio file simultaneously (WinError 32). Fixed
  to only retry `status=failed` jobs. Orphaned pending jobs from a crash are now
  adopted on next launch.
- Tiny trailing segment (< 8 KB / ~0.3 s) sent to OpenAI returned HTTP 400 "Audio
  file corrupted". Segments below the minimum size are now dropped before the API call.
- Fresh install (no API key): main window now shows on first launch so users can enter
  setup information. Subsequent launches and boot autostart remain tray-only.

## [0.1.0] - 2026-05-29

Initial public release.

### Added

**Core pipeline**
- Voice-to-text: hold or double-tap **Left Ctrl + Left Alt** to record; audio is
  transcribed by the OpenAI API, filler words are stripped, and the cleaned text is
  pasted at the cursor.
- Two activation modes: hold-to-record (release stops) and double-tap toggle (tap
  again to stop).
- Silence-aware segmented transcription — audio is split on silence gaps and
  transcribed in parallel during recording, delivering near-instant results on
  long dictations (Wispr Flow-style latency).
- OpenAI client reuse across calls (TLS/connection-pool kept alive — removes
  per-call handshake overhead).
- Max-recording cap: auto-stops a runaway recording at 10 minutes and toasts the
  user to start again. Configurable via `max_recording_sec` (0 disables).

**Text cleaning**
- Filler-word stripping: `uh`, `um`, `er`, `ah`, `you know`, `i mean`, `basically`,
  trailing `right`, leading `so`. `like` stripped only after a to-be verb.
- Sentence-aware capitalization: first letter and each sentence start uppercased.
- `dictionary` — user-defined spoken-word → replacement map (e.g. "cloud" → "Claude").
- `extra_fillers` — additional words/phrases to strip alongside built-ins.
- `voice_commands` (opt-in) — "comma", "period", "new line", "new paragraph", etc.
  become literal punctuation/whitespace.
- `code_mode` (opt-in) — disables auto-capitalize and auto-period for code dictation.
- `raw_mode` (opt-in) — delivers the verbatim transcript bypassing all cleaning.

**Paste modes**
- `clipboard` (default) — copies text then simulates Ctrl+V.
- `type` — types characters one-by-one via pynput (works in apps that block Ctrl+V,
  supports Unicode).
- `preserve_clipboard` — optionally restores the prior clipboard after paste.

**Undo / history**
- Tray "Paste Previous" — re-pastes the most recent transcription (last 5 kept
  in memory, cleared on exit).

**Settings & configuration**
- Settings dialog rebuilt as a 4-tab notebook: API · Recording · Behavior · Text.
- Language hint (`language`) — ISO-639-1 code passed to the OpenAI API to improve
  accuracy on accented or non-English speech (blank = auto-detect).
- Mic picker — choose a specific input device or use the system default.
- Visual editors for `extra_fillers` and `dictionary` (JSON textarea with
  validation feedback).
- Config validation with friendly load-time warnings for bad values.

**UI & tray**
- App starts tray-only — no window popup on launch.
- Animated recording overlay: 9-bar waveform, Gaussian bell-curve envelope
  (center bar tallest), audio-reactive at 25 fps, idle breathing animation.
- Transcribing overlay: slow traveling sine wave (distinct "thinking" look).
- Rounded pill shape with transparent corners (Windows native).
- Main window, tray icon (gray/red/yellow/orange), silent toasts.
- Start-on-login via per-user registry entry (default on).

**Reliability**
- Disk-backed retry queue: failed transcriptions retried automatically (max 3
  attempts, 60 s interval); manual retry from tray menu.
- Audio written to disk continuously — a crash mid-record leaves a recoverable
  partial OGG.
- Atomic queue writes (`os.replace`) — no corrupt state on power loss.

**Packaging & distribution**
- Standalone Windows build: PyInstaller onedir + Inno Setup → `VoiceFlow-Setup.exe`.
- Per-user install (no admin prompt).
- All data written to `%LOCALAPPDATA%\VoiceFlow\` (works in read-only Program Files).

### Privacy
- No transcript text is ever persisted; logs contain metadata only (timing, counts,
  filenames — never what was dictated).
- Audio is deleted immediately after a successful paste; kept only on failure for
  retry, then deleted after max attempts.
- The API key is stored locally in `config.json` and sent only to OpenAI; no
  telemetry or analytics of any kind.

[Unreleased]: https://github.com/apgodlike/voiceflow/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/apgodlike/voiceflow/releases/tag/v0.1.0
