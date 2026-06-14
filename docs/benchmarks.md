# Latency — why VoiceFlow feels instant

VoiceFlow transcribes in chunks **during** recording, so when you release the key
only the final chunk is left to process. The wait you feel is **flat — it does not
grow with how long you spoke.**

## Method

`tools/latency_bench.py` replays real recordings of increasing length through the
actual pipeline and measures **key-release → text-ready** on a 6-core / 12-thread
CPU (no GPU), int8 models. These are VoiceFlow's own numbers — not a comparison
against any other tool.

## Parakeet (`parakeet-tdt-0.6b`, default English engine)

| You spoke | Time to text |
|-----------|-------------:|
| 10 s | 0.6 s |
| 30 s | 0.9 s |
| 60 s | 0.9 s |
| 120 s | 1.0 s |

Under ~1 second, flat — a 2-minute dictation pastes about as fast as a 10-second
note.

## Whisper (`distil-medium.en`, optional engine)

| You spoke | Time to text |
|-----------|-------------:|
| 10 s | 4.2 s |
| 30 s | 4.2 s |
| 60 s | 4.3 s |
| 120 s | 4.2 s |

Also flat (~4 s) — the Whisper encoder is heavier per chunk, but only the final
chunk runs on release. Parakeet is the faster default.

## Notes

- Numbers scale with your CPU; the **flat** shape (independent of recording length)
  holds on any hardware, because the work overlaps recording.
- Reproduce: `python tools/latency_bench.py --engine parakeet` (or `--engine whisper`).
