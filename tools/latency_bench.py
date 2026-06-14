"""Latency benchmark: VoiceFlow chunked streaming vs transcribe-after-stop.

VoiceFlow transcribes in chunks *during* recording, so when you release the key
only the final chunk is left to process — the wait is flat regardless of how long
you spoke. Most local dictation tools transcribe the whole recording *after* you
stop, so their wait grows with recording length. This harness measures the
**key-release -> text-ready** latency for both, on the same model and CPU, using
real recordings.

Run:  venv\\Scripts\\python.exe tools\\latency_bench.py [--engine parakeet|whisper]
"""
import argparse
import glob
import os
import time

import soundfile as sf

REC_DIR = "data/recordings"
TARGET_LENGTHS = [10, 30, 60, 120, 180]  # seconds


def _load_engine(engine: str):
    """Return a transcribe(numpy_audio, sr) callable for the chosen engine."""
    if engine == "parakeet":
        import onnx_asr
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = max(1, (os.cpu_count() or 4) // 2)
        m = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v2", quantization="int8",
                                sess_options=so, providers=["CPUExecutionProvider"])
        return lambda a, sr: (m.recognize(a, sample_rate=sr) or "")
    else:
        from faster_whisper import WhisperModel
        m = WhisperModel("distil-medium.en", device="cpu", compute_type="int8",
                         cpu_threads=max(1, (os.cpu_count() or 4) // 2))

        def _w(a, sr):
            import soundfile as _sf
            _sf.write("__bench_tmp.wav", a, sr)
            segs, _ = m.transcribe("__bench_tmp.wav", beam_size=1, vad_filter=True,
                                   condition_on_previous_text=False)
            return " ".join(s.text for s in segs)
        return _w


def _source_audio():
    longest = max(glob.glob(f"{REC_DIR}/*.ogg"), key=os.path.getsize)
    a, sr = sf.read(longest, dtype="float32")
    if a.ndim > 1:
        a = a[:, 0]
    return a, sr


def _time(fn, a, sr):
    t = time.monotonic()
    fn(a, sr)
    return time.monotonic() - t


def _simulate_chunked(fn, audio, sr, chunk_s=15):
    """Replay VoiceFlow's pipeline: chunks transcribed during recording, single
    serialized worker. Returns the post-release tail = how long after the user
    releases the key until text is ready."""
    n = max(1, len(audio) // (chunk_s * sr) + 1)
    bounds = [(i * chunk_s * sr, min((i + 1) * chunk_s * sr, len(audio))) for i in range(n)]
    bounds = [(s, e) for s, e in bounds if e - s > sr // 2]
    comp = [_time(fn, audio[s:e], sr) for s, e in bounds]
    emit = [e / sr for s, e in bounds]
    free = 0.0
    finish = []
    for e, c in zip(emit, comp):
        start = max(e, free)
        free = start + c
        finish.append(free)
    release = len(audio) / sr
    return finish[-1] - release


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="parakeet", choices=["parakeet", "whisper"])
    args = ap.parse_args()

    fn = _load_engine(args.engine)
    src, sr = _source_audio()
    _time(fn, src[:2 * sr], sr)  # warm

    print(f"\nEngine: {args.engine} | CPU cores: {os.cpu_count()}")
    print(f"{'recording':>10} | {'VoiceFlow (time to text)':>24} | {'whole-file (ref)':>16}")
    print("-" * 58)
    for L in TARGET_LENGTHS:
        if L * sr > len(src):
            continue
        clip = src[:L * sr]
        whole = _time(fn, clip, sr)            # whole file in one call (reference only)
        chunked = _simulate_chunked(fn, clip, sr)
        print(f"{L:>8}s  | {chunked:>22.1f}s | {whole:>14.1f}s")
    if os.path.exists("__bench_tmp.wav"):
        os.remove("__bench_tmp.wav")
    print("\n(VoiceFlow stays flat — only the final chunk runs on release. whole-file column"
          "\n is a reference for the same model transcribing the entire clip at once.)")


if __name__ == "__main__":
    main()
