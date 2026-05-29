# VoiceFlow — Privacy Policy

_Last updated: May 2026_

VoiceFlow is a free, open-source Windows application. This policy describes exactly what data the app handles and where it goes.

## What VoiceFlow collects

VoiceFlow does **not** collect, store, or transmit any personal data to its developers. There is no analytics, no crash reporting, no usage tracking, and no account system.

## What stays on your machine

| Data | Where | Lifetime |
|------|-------|----------|
| OpenAI API key | `%LOCALAPPDATA%\VoiceFlow\config.json` | Until you remove it in Settings |
| Audio recordings | `%LOCALAPPDATA%\VoiceFlow\recordings\` | Deleted immediately after successful transcription |
| App settings | `%LOCALAPPDATA%\VoiceFlow\config.json` | Until uninstalled or manually deleted |
| Log file | `%LOCALAPPDATA%\VoiceFlow\voiceflow.log` | Rotating, max ~3 MB; metadata only |

**The log file never contains dictated text** — only timestamps, file sizes, and error messages.

**Audio on transcription failure:** if transcription fails, the audio file is kept so the job can be retried (automatically, up to 3 attempts). After the final failed attempt the audio is deleted. You can also trigger retry or see failed jobs from the tray menu.

## What leaves your machine

The only outbound network call VoiceFlow makes is:

> Audio → **OpenAI Transcription API** (api.openai.com) over HTTPS

Your audio is sent to OpenAI to be transcribed. OpenAI's handling of that audio is governed by [OpenAI's privacy policy](https://openai.com/policies/privacy-policy) and [API data usage policy](https://openai.com/policies/api-data-usage-policies). VoiceFlow uses your own API key — the developers of VoiceFlow never receive your audio or your key.

No other network calls are made. VoiceFlow does not phone home, check for updates, or send any telemetry.

## Third-party dependencies

VoiceFlow uses only well-known open-source libraries (sounddevice, soundfile, pynput, pyautogui, pystray, Pillow, pyperclip, openai-python, python-dotenv). None of these libraries send data to any third party on their own.

## Children

VoiceFlow is a general-purpose productivity tool with no features directed at children.

## Changes

If this policy changes, the updated version will be committed to the public repository at  
https://github.com/apgodlike/voiceflow/blob/main/docs/privacy.md

## Contact

Questions: open an issue at https://github.com/apgodlike/voiceflow/issues  
Security concerns: praveenap2402@gmail.com (see [SECURITY.md](../SECURITY.md))
