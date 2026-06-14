# Latency benchmark — why VoiceFlow feels instant

Most local dictation tools transcribe the whole recording **after** you stop, so
the wait grows with how long you spoke. VoiceFlow transcribes in chunks **during**
recording, so when you release the key only the final chunk is left to process —
**the wait is flat regardless of length.**

## Method

`tools/latency_bench.py` replays real recordings of increasing length through two
pipelines on the **same model and CPU** and measures **key-release → text-ready**:

- **after-stop** — transcribe the whole file in one call when recording stops
  (what Whisper-after-stop dictation tools do).
- **VoiceFlow chunked** — chunks transcribed during recording, one serialized
  worker; only the final chunk runs after release.

Measured on a 6-core / 12-thread CPU (no GPU), int8 models.

## Parakeet (`parakeet-tdt-0.6b`, default English engine)

| You spoke | After-stop (others) | **VoiceFlow chunked** |
|-----------|--------------------:|----------------------:|
| 10 s | 0.6 s | **0.6 s** |
| 30 s | 2.0 s | **0.9 s** |
| 60 s | 4.6 s | **0.9 s** |
| 120 s | 11.4 s | **1.0 s** |

## Whisper (`distil-medium.en`)

| You spoke | After-stop (others) | **VoiceFlow chunked** |
|-----------|--------------------:|----------------------:|
| 10 s | 4.1 s | **4.2 s** |
| 30 s | 4.6 s | **4.2 s** |
| 60 s | 13.2 s | **4.3 s** |
| 120 s | 22.3 s | **4.2 s** |

## Takeaway

The longer you dictate, the bigger the gap. At 2 minutes, VoiceFlow pastes in
**~1 s (Parakeet)** while an after-stop tool makes you wait **~11 s** — and ~4 s vs
**~22 s** on Whisper. For short notes the difference is small; for real paragraphs
and long-form dictation it's the difference between "instant" and "go get coffee".

Reproduce: `python tools/latency_bench.py --engine parakeet` (or `--engine whisper`).
Numbers scale with your CPU; the *flat-vs-growing* shape holds everywhere.
