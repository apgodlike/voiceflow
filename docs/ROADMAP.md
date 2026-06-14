# VoiceFlow Roadmap

Living doc of what's done, what's next, and known limits. Updated 2026-06-14.

## Shipped — v0.2.7 (local Whisper backend)

- **Local transcription backend** via faster-whisper — offline, no API key, no
  cloud, no cost. First-run wizard picks Cloud (OpenAI) or Local; tray toggles live.
- **Curated model menu (5):** `distil-medium.en` (default), `distil-small.en`,
  `distil-large-v3`, plus `small`/`medium` for non-English. `config.json` still
  accepts any faster-whisper model by hand.
- **Flat local latency.** Transcribes in ~12-15 s chunks *during* recording, so on
  release only the final chunk is processed. Post-release wait is independent of
  recording length (a 3-min dictation ≈ a 10-s one). On a 6-core CPU that's ~3-4 s
  with `distil-medium.en`. *The flatness is universal; the absolute number scales
  with CPU and model.*
- Hardware-aware model recommendation, English-only `.en` + distil variants,
  remove-downloaded-model from Settings, physical-core thread pinning.
- Fixes: windowed-build `NoneType.write` download crash; double-paste safety.

## Next — Parakeet / Moonshine spike (the large-accuracy-at-speed question)

**Why:** any Whisper *large* model has a ~12.5 s encoder floor per call on CPU
(no GPU) — measured, irreducible. distil-medium.en (~3-4 s) is the practical CPU
ceiling for Whisper. The only path to large-class accuracy at ~3-5 s on CPU is a
different engine.

**Plan (spike first, integrate later):**
1. Isolated throwaway venv (`venv-parakeet/`, gitignored) — **must not** touch the
   shipped app's deps (NeMo/PyTorch is ~2-3 GB; would bloat the 78 MB installer).
2. Install `nemo_toolkit[asr]` (Parakeet-TDT-0.6B) — and/or Moonshine via
   onnxruntime as the lighter alternative.
3. Benchmark the same 90 s reference clip on this CPU: RTF, post-release feel,
   accuracy vs `distil-medium.en` / `distil-large-v3`.
4. Decide integration: if it wins, add as an optional 3rd backend with a separate
   on-demand model download — **not** bundled into the core installer.

## Backlog

- **Code signing** — reapply to SignPath Foundation once the repo has traction
  (stars + a citable thread). Release pipeline is pre-wired; just add 2 secrets.
- **winget** package (`winget install VoiceFlow`) alongside Scoop.
- **Sentence-fragment polish** — chunk-boundary capitalization can create false
  breaks ("…slush. Which…"). Whisper per-chunk casing; needs a smarter stitch.
- **Cost-comparison math** in README for the cloud (BYO-key) path.

## Known limits (CPU, no GPU)

- Whisper `large` variants (incl. turbo, distil-large): ~12.5 s/call floor —
  can't beat ~13-20 s on CPU. Use medium or smaller for snappy dictation.
- Absolute latency scales with CPU core count and model size; old/2-core machines
  are slower. The *flat-with-length* property holds everywhere.
