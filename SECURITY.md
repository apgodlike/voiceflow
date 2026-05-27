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

- **API key** — stored locally in `%LOCALAPPDATA%\VoiceFlow\config.json`. It is
  never logged and never sent anywhere except OpenAI over HTTPS.
- **No transcript storage** — recognized text is pasted and never written to disk.
- **Audio** — recorded to `%LOCALAPPDATA%\VoiceFlow\recordings` and deleted
  immediately after a successful paste. Audio is kept only when a transcription
  fails, so the job can be retried.
- **Logs** — `%LOCALAPPDATA%\VoiceFlow\voiceflow.log` records only metadata
  (timings, counts, errors). It never contains what you dictated.
- **No telemetry** — the app makes no network calls other than to the OpenAI API.

## Audio leaves your machine

Transcription uses the OpenAI API, so audio is uploaded to OpenAI for processing.
Review OpenAI's data usage policy if this matters for your use case. Everything
else stays local.

## Supported versions

VoiceFlow is pre-1.0. Only the latest release receives security fixes.
