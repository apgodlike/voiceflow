"""Local backend skips the per-segment fast-path and transcribes the whole file
once on stop; the OpenAI backend keeps segmenting. These tests pin that routing
so the speed fix can't silently regress."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import voiceflow.main as main


@pytest.fixture
def app(tmp_path):
    """Construct App with all GUI/IO collaborators mocked out."""
    cfg = dict(
        backend="openai", openai_api_key="sk-test", local_model="distil-small.en",
        language="", model="gpt-4o-mini-transcribe",
    )
    with patch.object(main, "UI"), patch.object(main, "Tray"), \
         patch.object(main, "HotkeyController"), \
         patch.object(main.config, "load", return_value=cfg), \
         patch.object(main.config, "save"), \
         patch.object(main.transcriber, "reset_client"):
        a = main.App()
    a._executor = MagicMock()          # capture submit() without running threads
    a._cfg = cfg
    return a


def _seg(tmp_path, name="r.seg0.ogg", size=20_000):
    p = tmp_path / name
    p.write_bytes(b"\x00" * size)
    return p


def test_openai_segment_submits_transcription(app, tmp_path):
    app._cfg["backend"] = "openai"
    p = _seg(tmp_path)
    app._on_segment(0, p)
    app._executor.submit.assert_called_once()
    assert app._seg_futures and app._seg_paths[0] == p


def test_local_segment_tracks_path_but_does_not_transcribe(app, tmp_path):
    app._cfg["backend"] = "local"
    p = _seg(tmp_path)
    app._on_segment(0, p)
    app._executor.submit.assert_not_called()      # no per-segment transcription
    assert app._seg_paths[0] == p                 # still tracked for cleanup
    assert 0 not in app._seg_futures


def test_tiny_segment_is_dropped(app, tmp_path):
    app._cfg["backend"] = "openai"
    p = _seg(tmp_path, size=100)                   # below _MIN_SEGMENT_BYTES
    app._on_segment(0, p)
    app._executor.submit.assert_not_called()
    assert not p.exists()


@pytest.mark.parametrize("backend,expected", [
    ("local", "_finalize_local"),
    ("openai", "_finalize_job"),
])
def test_on_stop_routes_by_backend(app, tmp_path, backend, expected):
    app._cfg["backend"] = backend
    app._current_rid = "rid123"
    full = tmp_path / "rid123.ogg"
    full.write_bytes(b"\x00" * 100)
    started = {}

    class FakeThread:
        def __init__(self, target, args, **kw):
            started["target"] = target
            started["args"] = args
        def start(self):
            pass

    with patch.object(main.recorder, "stop_recording", return_value=full), \
         patch.object(main.q, "enqueue"), \
         patch.object(main.threading, "Thread", FakeThread):
        app._on_stop()

    assert started["target"].__name__ == expected
