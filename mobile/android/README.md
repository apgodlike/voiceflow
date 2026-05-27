# VoiceFlow for Android

Floating mic button → speak → transcribed text copied to the clipboard. Long-press
any text field and paste. Mirrors the desktop VoiceFlow pipeline
(record → transcribe → clean → output), clipboard-only — no custom keyboard, no
accessibility service.

## How it works

1. A draggable, semi-transparent bubble floats over every app
   (`SYSTEM_ALERT_WINDOW` + a foreground service of type `microphone`).
2. Tap the bubble → record (`MediaRecorder`, 16 kHz mono AAC/m4a).
3. Tap again → stop, upload to the OpenAI transcription endpoint, run the same
   filler-stripping cleaner as desktop, copy the result to the clipboard.
4. Bubble colour = state: gray idle · red recording · yellow transcribing ·
   green copied · red error.

Audio is written to the app cache and deleted right after transcription. The
dictated text is never logged or persisted (privacy parity with desktop).

## Build & run

Open `mobile/android/` in Android Studio (Giraffe+), let it sync, then Run on a
device/emulator (min SDK 29 / Android 10).

From the CLI (needs a local SDK and the Gradle wrapper jar, which Android Studio
generates on first sync):

```bash
./gradlew :app:assembleDebug        # build APK
./gradlew :app:test                 # run CleanerTest unit tests
./gradlew :app:installDebug         # install on connected device
```

## First-run setup (in the app)

1. Paste your OpenAI API key (stored encrypted via `EncryptedSharedPreferences`).
2. Grant **Draw over other apps**, **Microphone**, and (Android 13+)
   **Notifications**.
3. Tap **Start floating button**.

## Config

- **Model** — defaults to `gpt-4o-mini-transcribe`; editable in the app.
- **API key** — bring your own; no backend or account.

## Status

Phase 1. iOS is intentionally deferred — iOS sandboxing forbids a system-wide
floating overlay, so the same UX isn't achievable there.
