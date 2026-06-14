# Security Policy

## Reporting a vulnerability

Please do **not** open a public issue for security problems.

- Preferred: open a private advisory at
  https://github.com/apgodlike/voiceflow/security/advisories/new
- Or email: praveenap2402@gmail.com

Include steps to reproduce and the impact. You'll get an acknowledgement as soon
as possible, and a fix or mitigation will be coordinated before public disclosure.

## How VoiceFlow handles your data

VoiceFlow is designed to keep your data on your machine:

- **API key** (cloud mode only) — stored locally in the app data dir's
  `config.json`. It is never logged and never sent anywhere except OpenAI over HTTPS.
- **No transcript storage** — recognized text is pasted and never written to disk.
- **Audio** — recorded to the app data dir and deleted immediately after a
  successful paste. Audio is kept only when a transcription fails, so the job can
  be retried.
- **Logs** — `voiceflow.log` records only metadata (timings, counts, errors). It
  never contains what you dictated.
- **No telemetry** — the app sends no analytics or usage data anywhere.

## Where audio goes (depends on mode)

- **Local mode (the default — Parakeet or Whisper):** audio is transcribed entirely
  on your machine. **No audio leaves your computer.** The only network access is a
  one-time model download from Hugging Face (model files, never your audio).
- **Cloud mode (OpenAI):** if you choose the OpenAI backend, recording audio is
  uploaded to the OpenAI API for transcription — review OpenAI's data usage policy.
- **Optional AI text cleanup (off by default):** sends the transcribed *text* (not
  audio) to a local Ollama server or to OpenAI, whichever you choose.

Everything else stays local.

## Supported versions

VoiceFlow is pre-1.0. Only the latest release receives security fixes.
