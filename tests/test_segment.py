"""Tests for silence-aware segmentation — _SegmentCutter (pure) + recorder wiring."""
from unittest.mock import patch

import numpy as np
import soundfile as sf

from voiceflow.recorder import _SegmentCutter

# Small, fast params: at 1000 Hz, 1 frame == 1 ms.
CUTTER_KW = dict(
    sample_rate=1000,
    silence_threshold=300.0,
    silence_min_ms=100,
    segment_min_ms=200,
    segment_max_ms=500,
)
LOUD = 1000.0
QUIET = 0.0


def test_no_cut_before_segment_min():
    c = _SegmentCutter(**CUTTER_KW)
    # 150 ms of silence — below segment_min (200 ms) → no cut yet.
    assert c.feed(QUIET, 100) is False
    assert c.feed(QUIET, 50) is False


def test_cut_on_silence_after_min():
    c = _SegmentCutter(**CUTTER_KW)
    assert c.feed(LOUD, 200) is False           # seg=200, no silence
    assert c.feed(QUIET, 50) is False            # silence=50 < 100
    assert c.feed(QUIET, 50) is True             # silence=100 ≥ 100, seg≥200 → cut


def test_force_cut_at_max_even_without_silence():
    c = _SegmentCutter(**CUTTER_KW)
    assert c.feed(LOUD, 200) is False
    assert c.feed(LOUD, 200) is False            # seg=400 < 500
    assert c.feed(LOUD, 100) is True             # seg=500 ≥ max → cut despite loud


def test_counters_reset_after_cut():
    c = _SegmentCutter(**CUTTER_KW)
    c.feed(LOUD, 200)
    assert c.feed(QUIET, 100) is True            # cut → counters reset
    # Fresh segment: 150 ms silence is below segment_min again → no immediate cut.
    assert c.feed(QUIET, 100) is False
    assert c.feed(QUIET, 50) is False


def test_silence_run_breaks_on_loud():
    c = _SegmentCutter(**CUTTER_KW)
    c.feed(LOUD, 200)
    c.feed(QUIET, 80)                            # silence=80
    c.feed(LOUD, 10)                             # loud resets silence to 0
    assert c.feed(QUIET, 80) is False            # silence only 80 again


class _FakeStream:
    def __init__(self, **kwargs):
        _FakeStream.callback = kwargs.get("callback")

    def start(self): pass
    def stop(self): pass
    def close(self): pass


def test_recorder_emits_ordered_segments(tmp_path):
    """Driving the real callback through cuts emits segments 0,1,2 in order."""
    seen: list[tuple[int, str]] = []

    with patch("voiceflow.recorder.RECORDINGS_DIR", tmp_path), \
         patch("voiceflow.recorder.sd.InputStream", _FakeStream):
        from voiceflow import recorder
        recorder._active.clear()

        rid = recorder.start_recording(on_segment=lambda i, p: seen.append((i, str(p))))
        cb = _FakeStream.callback

        n = recorder.SAMPLE_RATE  # 1 s blocks at the real rate
        loud = np.full((n, 1), 5000, dtype="int16")
        quiet = np.zeros((n, 1), dtype="int16")

        for block in (loud, loud, loud, loud, quiet):  # ~4 s speech + pause → cut 0
            cb(block, n, None, None)
        for block in (loud, loud, loud, loud, quiet):  # → cut 1
            cb(block, n, None, None)
        cb(loud, n, None, None)                         # short trailing segment

        recorder.stop_recording(rid)                    # emits final segment 2

    indices = [i for i, _ in seen]
    assert indices == [0, 1, 2], f"segments out of order: {indices}"
    for _, path in seen:
        info = sf.info(path)
        assert info.samplerate == 16000 and info.channels == 1
