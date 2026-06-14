"""Parakeet validation harness (NOT shipped — spike/eval only).

Runs the pre-prod checks for the Parakeet local engine: throttled "floor machine"
cold-start + timing, chunk lag, silence/noise/garbage behavior, memory, and dumps
transcripts of real recordings for accuracy review against Whisper.

Run in the isolated venv:  venv-parakeet\\Scripts\\python.exe tools\\parakeet_eval.py
"""
import glob
import os
import time

import numpy as np
import psutil
import soundfile as sf

import onnx_asr
import onnxruntime as ort

SR = 16000
MODEL = "nemo-parakeet-tdt-0.6b-v2"
REC_DIR = "data/recordings"


def _rss_mb() -> float:
    return psutil.Process().memory_info().rss / 1024 / 1024


def _read(path):
    a, sr = sf.read(path, dtype="float32")
    if a.ndim > 1:
        a = a[:, 0]
    return a, sr


def load(threads: int | None, quant: str | None):
    so = ort.SessionOptions()
    if threads:
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
    t0 = time.monotonic()
    m = onnx_asr.load_model(MODEL, quantization=quant, sess_options=so,
                            providers=["CPUExecutionProvider"])
    return m, time.monotonic() - t0


def t_recognize(m, audio):
    s = time.monotonic()
    txt = m.recognize(audio, sample_rate=SR)
    return txt, time.monotonic() - s


def main():
    print(f"=== Parakeet eval | host cores={os.cpu_count()} ===\n")

    # pick a long real recording for slicing
    longs = sorted(glob.glob(f"{REC_DIR}/*.ogg"),
                   key=lambda f: os.path.getsize(f), reverse=True)
    src, sr = _read(longs[0])
    dur = len(src) / sr
    print(f"slice source: {os.path.basename(longs[0])} ({dur:.0f}s)\n")

    # 1 + 5. cold load + memory, full vs default threads; try int8 quant
    rss0 = _rss_mb()
    for quant in (None, "int8"):
        try:
            m, load_s = load(threads=None, quant=quant)
            _ = t_recognize(m, src[:2 * sr])  # warm
            print(f"[load] quant={quant or 'fp32':5} cold_load={load_s:5.1f}s  "
                  f"RSS_after_load={_rss_mb()-rss0:6.0f}MB")
            del m
        except Exception as e:
            print(f"[load] quant={quant}: ERROR {e}")

    # default-thread model for the rest
    m, _ = load(threads=None, quant=None)
    t_recognize(m, src[:2 * sr])

    # 2. floor machine: throttle to 2 intra-op threads, cold start, 30s clip
    print()
    mf, load_s = load(threads=2, quant=None)
    clip30 = src[30 * sr:60 * sr]
    t_recognize(mf, src[:2 * sr])  # warm
    _, el = t_recognize(mf, clip30)
    print(f"[floor 2-thread] cold_load={load_s:.1f}s  30s_clip={el:.2f}s "
          f"(RTF {el/30:.2f})")
    del mf

    # default-thread timings by length (chunk-lag + tail)
    print()
    for ch in (5, 15, 30, 60):
        arr = src[30 * sr:(30 + ch) * sr]
        if len(arr) < sr:
            continue
        _, el = t_recognize(m, arr)
        print(f"[default-thread] {ch:2d}s -> {el:.2f}s (RTF {el/ch:.2f})")

    # 4. silence / noise / garbage -> should stay quiet
    print()
    silence = np.zeros(5 * sr, dtype=np.float32)
    noise = (np.random.randn(5 * sr) * 0.1).astype(np.float32)
    tone = (0.3 * np.sin(2 * np.pi * 440 * np.arange(5 * sr) / sr)).astype(np.float32)
    for name, a in (("silence", silence), ("white-noise", noise), ("440Hz-tone", tone)):
        txt, _ = t_recognize(m, a)
        print(f"[garbage] {name:11} -> {txt!r}")

    # 3. real recordings -> dump transcripts for accuracy review
    print("\n[real-audio] transcripts -> tools/eval_parakeet.txt")
    files = sorted(glob.glob(f"{REC_DIR}/*.ogg"))[:12]
    with open("tools/eval_parakeet.txt", "w", encoding="utf-8") as fh:
        for f in files:
            a, sr = _read(f)
            if len(a) / sr < 2:
                continue
            txt, el = t_recognize(m, a)
            fh.write(f"### {os.path.basename(f)} ({len(a)/sr:.0f}s, {el:.1f}s)\n{txt}\n\n")
    print("done.")


if __name__ == "__main__":
    main()
