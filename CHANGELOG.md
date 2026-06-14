# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.3.1] - 2026-06-14

### Changed
- Raised the recording auto-stop cap from 10 → **30 minutes** (still a safety net
  against a forgotten toggle / stuck key; `max_recording_sec: 0` disables it).
- **Docs synced to the Parakeet-default reality.** The first-run wizard, README,
  and config reference said "Local — Whisper" / "runs Whisper" even though
  Parakeet is the default engine — now corrected throughout. `docs/privacy.md`
  fixed its core claim: local mode (the default) sends **no audio** anywhere; only
  cloud mode sends audio to OpenAI; documents the one-time model download and the
  optional AI-cleanup data flow. The OpenAI-key guide notes a key is cloud-only;
  ROADMAP marks Parakeet shipped; `CLAUDE.md` documents the three-backend dispatch.

## [0.3.0] - 2026-06-14

### Added
- **Parakeet local engine** — NVIDIA Parakeet-TDT-0.6B (via `onnx-asr` +
  `onnxruntime`, no PyTorch/NeMo, +42 MB) is the new **default** English engine.
  Unlike Whisper it has no fixed encoder window, so a 30 s clip transcribes in
  ~2 s with no per-call floor — fast even throttled to 2 cores (~2.75 s) — and it
  stays *silent* on background noise/silence instead of hallucinating text. On the
  maintainer's real accented recordings it beat `distil-medium.en` on both words
  and punctuation. English-only; Whisper `small`/`medium` remain for other
  languages. Downloads the ~660 MB int8 model on first use; ~760 MB RAM.
- **Cross-platform install via pipx** — `pipx install "voiceflow-dictation[local]"`
  runs on Windows, macOS, and Linux from source (no signing, no SmartScreen).
  Additive: the Windows `.exe`/Scoop build is unchanged. Includes macOS/Linux
  support in the data-dir and start-on-login logic.
- **Optional AI text cleanup** — opt-in LLM pass (local Ollama by default, or
  OpenAI) that polishes grammar/format after the rule-based cleaner. Off by
  default and fails open (never loses a dictation).
- **Red REC indicator** on the recording overlay so the state is unmistakable
  (silent — no sound notifications).
- Latency benchmark (`tools/latency_bench.py`) + `docs/benchmarks.md`: ~1 s to
  text on the default engine, flat regardless of recording length.

### Changed
- Default local model is now `parakeet`; the local model dropdown lists it first,
  with the Whisper models below.

### Notes
- Parakeet weights are © NVIDIA, licensed CC-BY-4.0 (attribution in `NOTICE` and
  the README). VoiceFlow and all libraries remain MIT.

## [0.2.7] - 2026-06-14

### Changed
- Trimmed the local model dropdown to 5 curated choices (was 12): `distil-medium.en`
  (recommended default), `distil-small.en`, `distil-large-v3`, and `small`/`medium`
  for non-English. `config.json` still accepts any faster-whisper model if edited
  by hand — this only declutters the menu.
- Default local model is now `distil-medium.en` — the fast + accurate sweet spot
  for English dictation (~3-4 s, flat regardless of recording length).

## [0.2.6] - 2026-06-14

### Changed
- Local chunk size now scales with the chosen model so the during-recording
  pipeline keeps pace with speech. Large models pay a large fixed per-call
  encoder cost (large-v3 ~12.5 s on a 6-core CPU, *regardless of clip length* —
  it can't be reduced by quantization, VAD, or chunk size), so they use ~24-28 s
  chunks to amortize it; medium/small keep ~12-15 s. This keeps a large model's
  latency flat (~13 s) across recording length instead of growing linearly, but
  note a large model cannot beat its ~12.5 s encoder floor on CPU — for snappy
  (~3-4 s) dictation use a medium or smaller model.

## [0.2.5] - 2026-06-14

### Changed
- **Local transcription latency is now flat (~3-4 s) regardless of recording
  length.** Whisper's encoder always runs a full ~30 s window per call, so many
  tiny silence-cut segments each re-paid that fixed cost (a 25 s dictation could
  take ~20 s+). Local now uses larger ~12-15 s chunks transcribed *during*
  recording: each chunk amortizes the encoder cost and processes ~4-5x faster
  than real time, so it keeps pace with speech and only the final chunk is left
  to process on release. Measured post-release wait: ~3.6 s for a 10 s, 60 s, or
  3-minute recording alike (distil-medium.en on a 6-core CPU). The OpenAI backend
  keeps smaller chunks (network-bound, parallelizes).
- Local inference pins CTranslate2 to physical cores instead of its auto setting,
  which over-subscribes hyper-threaded CPUs (~15% faster in testing).
- Default local model is now `distil-small.en` (fast + good English accuracy);
  the wizard recommends `distil-medium.en` on capable multi-core machines.

## [0.2.3] - 2026-06-14

### Added
- **Local transcription backend** — run Whisper on your own PC via
  `faster-whisper`, no OpenAI API key, no cloud, no cost. A first-run setup
  wizard lets you choose Cloud (OpenAI) or Local, downloads the model with a
  progress bar, and the tray menu toggles backends live.
- English-only (`.en`) model variants (`tiny.en`/`base.en`/`small.en`/`medium.en`):
  same download size, faster and more accurate for English than the multilingual
  model of the same size. Multilingual models remain for other languages.
- Distil-Whisper models (`distil-small.en`, `distil-medium.en`, `distil-large-v3`):
  knowledge-distilled, English-only, ~2-4x faster than the full model with
  near-identical English accuracy. `distil-large-v3` gives large-class accuracy
  without large's 3-4x-realtime CPU cost (there is no plain `large.en` — large is
  multilingual only, so the distilled model is the fast English option).
- Hardware-aware model recommendation in the wizard — pre-selects `medium.en` on
  capable multi-core machines, `small.en` otherwise, based on CPU core count.
- Remove a downloaded model from Settings to free disk space (re-downloadable
  anytime).

### Changed
- Default local model is `small.en` (safe on any hardware); the wizard upgrades
  the recommendation to `medium.en` on capable CPUs.
- Local inference uses `condition_on_previous_text=False` — faster per segment
  and avoids silence-driven hallucination loops.

### Fixed
- Windowed (no-console) build crashed local model downloads with
  `'NoneType' object has no attribute 'write'`: `sys.stdout`/`sys.stderr` are
  `None` when frozen, and huggingface_hub's tqdm progress bar wrote to them.
  `run.py` now redirects the missing streams to the null device at startup.

## [0.1.4] - 2026-06-13

### Added
- Scoop install: `scoop bucket add voiceflow https://github.com/apgodlike/voiceflow`
  then `scoop install voiceflow`. Scoop verifies the download by SHA-256, so the
  Windows SmartScreen "Unknown publisher" prompt is skipped entirely — no
  code-signing certificate required.
- Portable zip release asset (`VoiceFlow-portable-*.zip`) plus a `.sha256`
  sidecar: unzip and run `VoiceFlow.exe`, no installer. This is also the Scoop
  install source (deterministic layout). The release workflow self-maintains the
  Scoop manifest (version + url + hash) on each tag.

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
