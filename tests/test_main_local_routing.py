"""Both backends transcribe segments during recording (overlap), but the local
Whisper backend uses larger chunks so each amortizes its fixed ~30 s-window
encoder cost; OpenAI uses smaller chunks for more parallelism. These tests pin
that chunk-size routing and the empty-futures fallback."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import voiceflow.main as main


@pytest.fixture
def app():
    """Construct App with all GUI/IO collaborators mocked out."""
    cfg = dict(
        backend="openai", openai_api_key="sk-test", local_model="distil-small.en",
        language="", model="gpt-4o-mini-transcribe", input_device=None,
    )
    with patch.object(main, "UI"), patch.object(main, "Tray"), \
         patch.object(main, "HotkeyController"), \
         patch.object(main.config, "load", return_value=cfg), \
         patch.object(main.config, "save"), \
         patch.object(main.transcriber, "reset_client"):
        a = main.App()
    a._executor = MagicMock()
    a._cfg = cfg
    return a


def _seg(tmp_path, name="r.seg0.ogg", size=20_000):
    p = tmp_path / name
    p.write_bytes(b"\x00" * size)
    return p


def test_segment_submits_transcription_both_backends(app, tmp_path):
    for backend in ("openai", "local"):
        app._cfg["backend"] = backend
        app._executor.reset_mock()
        app._seg_futures, app._seg_paths = {}, {}
        app._on_segment(0, _seg(tmp_path, name=f"{backend}.seg0.ogg"))
        app._executor.submit.assert_called_once()
        assert 0 in app._seg_futures


def test_tiny_segment_is_dropped(app, tmp_path):
    p = _seg(tmp_path, size=100)  # below _MIN_SEGMENT_BYTES
    app._on_segment(0, p)
    app._executor.submit.assert_not_called()
    assert not p.exists()


def test_on_start_openai_uses_recorder_defaults(app):
    app._cfg["backend"] = "openai"
    captured = {}
    with patch.object(main.recorder, "start_recording",
                      side_effect=lambda **kw: captured.update(kw) or "rid"):
        app._on_start()
    assert captured["segment_min_ms"] == main.recorder.SEGMENT_MIN_MS
    assert captured["segment_max_ms"] == main.recorder.SEGMENT_MAX_MS


@pytest.mark.parametrize("model,expected", [
    ("distil-small.en", (12000, 15000)),
    ("medium.en", (12000, 15000)),
    ("distil-large-v3", (24000, 28000)),
    ("large", (24000, 28000)),
])
def test_on_start_local_chunk_size_scales_with_model(app, model, expected):
    app._cfg["backend"] = "local"
    app._cfg["local_model"] = model
    captured = {}
    with patch.object(main.recorder, "start_recording",
                      side_effect=lambda **kw: captured.update(kw) or "rid"):
        app._on_start()
    assert (captured["segment_min_ms"], captured["segment_max_ms"]) == expected


@pytest.mark.parametrize("model,engine_mod", [
    ("parakeet", "voiceflow.transcriber_parakeet"),
    ("distil-medium.en", "voiceflow.transcriber_local"),
])
def test_local_transcribe_dispatches_engine_by_model(app, tmp_path, model, engine_mod):
    app._cfg["backend"] = "local"
    app._cfg["local_model"] = model
    audio = tmp_path / "a.ogg"
    audio.write_bytes(b"\x00" * 100)
    import importlib
    mod = importlib.import_module(engine_mod)
    with patch.object(mod, "transcribe", return_value="hi") as tr, \
         patch.object(mod, "is_loaded", return_value=True):
        out = app._transcribe(audio)
    assert out == "hi"
    tr.assert_called_once()


def test_on_stop_empty_futures_falls_back_to_full_file(app, tmp_path):
    """If no segments were collected, the whole file is transcribed rather than
    the recording being silently dropped."""
    app._cfg["backend"] = "local"
    full = tmp_path / "rid.ogg"
    full.write_bytes(b"\x00" * 100)
    with patch.object(app, "_process_job") as pj, \
         patch.object(app, "_cleanup_segments"):
        app._finalize_job("rid", full, futures={}, seg_paths={})
    pj.assert_called_once_with("rid", full)
