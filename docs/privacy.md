# VoiceFlow — Privacy Policy

_Last updated: June 2026_

VoiceFlow is a free, open-source voice-typing app (Windows, with macOS/Linux via pipx). This policy describes exactly what data the app handles and where it goes.

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

This depends on the mode you choose.

**Local mode (the default — Parakeet or Whisper):** your audio is transcribed entirely on your own machine. **No audio ever leaves your computer.** The only network access is a **one-time model download** the first time you select a model — the model files are fetched from Hugging Face; your audio is never uploaded.

**Cloud mode (OpenAI):** if you switch the backend to OpenAI, each recording's audio is sent to the OpenAI Transcription API to be transcribed:

> Audio → **OpenAI Transcription API** (api.openai.com) over HTTPS

OpenAI's handling of that audio is governed by [OpenAI's privacy policy](https://openai.com/policies/privacy-policy) and [API data usage policy](https://openai.com/policies/api-data-usage-policies). VoiceFlow uses your own API key — the developers of VoiceFlow never receive your audio or your key.

**Optional AI text cleanup (off by default):** if you enable it, the transcribed *text* (not audio) is sent to the provider you choose — a **local Ollama** server (stays on your machine) or **OpenAI** (sent to api.openai.com).

Apart from the above, VoiceFlow makes no network calls — it does not phone home, send telemetry, or check for updates.

## Third-party dependencies

VoiceFlow uses only well-known open-source libraries (sounddevice, soundfile, pynput, pyautogui, pystray, Pillow, pyperclip, python-dotenv, requests, and the local speech engines faster-whisper / CTranslate2 and onnx-asr / onnxruntime, plus huggingface_hub for one-time model downloads; openai-python only for cloud mode). None of these send data to any third party on their own — `huggingface_hub` contacts Hugging Face only to download the model you pick.

## Children

VoiceFlow is a general-purpose productivity tool with no features directed at children.

## Changes

If this policy changes, the updated version will be committed to the public repository at  
https://github.com/apgodlike/voiceflow/blob/main/docs/privacy.md

## Contact

Questions: open an issue at https://github.com/apgodlike/voiceflow/issues  
Security concerns: praveenap2402@gmail.com (see [SECURITY.md](../SECURITY.md))
