"""Tests for recorder.py — monkeypatched sounddevice + soundfile."""
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf


def test_wav_written_and_nonzero(tmp_path):
    """start_recording → stop_recording writes a valid non-empty WAV."""
    captured_callback = {}

    class FakeInputStream:
        def __init__(self, **kwargs):
            captured_callback["cb"] = kwargs.get("callback")

        def start(self):
            pass

        def stop(self):
            pass

        def close(self):
            pass

    with patch("voiceflow.recorder.RECORDINGS_DIR", tmp_path), \
         patch("voiceflow.recorder.sd.InputStream", FakeInputStream):
        from voiceflow import recorder

        rid = recorder.start_recording()
        cb = captured_callback["cb"]
        fake_audio = np.zeros((512, 1), dtype="int16")
        fake_audio[0] = 32767
        cb(fake_audio, 512, None, None)
        path = recorder.stop_recording(rid)

    assert path.exists(), "WAV file not created"
    assert path.stat().st_size > 44, "WAV file too small (header only?)"
    info = sf.info(str(path))
    assert info.samplerate == 16000
    assert info.channels == 1


def test_recording_id_unique():
    """Each call to start_recording returns a different id."""
    ids = set()

    class FakeInputStream:
        def __init__(self, **kwargs):
            captured_callback = kwargs.get("callback")

        def start(self): pass
        def stop(self): pass
        def close(self): pass

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with patch("voiceflow.recorder.RECORDINGS_DIR", tmp_path), \
             patch("voiceflow.recorder.sd.InputStream", FakeInputStream):
            from voiceflow import recorder
            for _ in range(3):
                rid = recorder.start_recording()
                ids.add(rid)
                recorder.stop_recording(rid)

    assert len(ids) == 3


def test_stop_removes_from_active(tmp_path):
    """stop_recording pops entry from _active dict."""
    class FakeInputStream:
        def __init__(self, **kwargs): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass

    with patch("voiceflow.recorder.RECORDINGS_DIR", tmp_path), \
         patch("voiceflow.recorder.sd.InputStream", FakeInputStream):
        from voiceflow import recorder
        recorder._active.clear()
        rid = recorder.start_recording()
        assert rid in recorder._active
        recorder.stop_recording(rid)
        assert rid not in recorder._active
