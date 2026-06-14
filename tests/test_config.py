"""Tests for config.py — load/save round-trip + key/model precedence."""
from unittest.mock import patch

from voiceflow import config


def test_load_returns_defaults_when_missing(tmp_path):
    with patch("voiceflow.paths.CONFIG_PATH", tmp_path / "config.json"):
        cfg = config.load()
    assert cfg == config.DEFAULTS
    assert cfg is not config.DEFAULTS  # must be a copy


def test_save_then_load_round_trip(tmp_path):
    cfg_path = tmp_path / "config.json"
    with patch("voiceflow.paths.CONFIG_PATH", cfg_path):
        config.save({**config.DEFAULTS, "openai_api_key": "sk-test", "model": "gpt-4o-transcribe"})
        loaded = config.load()
    assert loaded["openai_api_key"] == "sk-test"
    assert loaded["model"] == "gpt-4o-transcribe"


def test_load_tolerates_corrupt_file(tmp_path):
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("{not valid json", encoding="utf-8")
    with patch("voiceflow.paths.CONFIG_PATH", cfg_path):
        cfg = config.load()
    assert cfg == config.DEFAULTS


def test_resolved_api_key_prefers_config_over_env():
    with patch.dict("os.environ", {"OPENAI_API_KEY": "from-env"}):
        assert config.resolved_api_key({"openai_api_key": "from-config"}) == "from-config"
        assert config.resolved_api_key({"openai_api_key": ""}) == "from-env"


def test_resolved_model_falls_back_to_default():
    with patch.dict("os.environ", {}, clear=True):
        assert config.resolved_model({}) == config.DEFAULTS["model"]
        assert config.resolved_model({"model": "gpt-4o-transcribe"}) == "gpt-4o-transcribe"


def test_max_recording_cap_default_is_thirty_minutes():
    assert config.DEFAULTS["max_recording_sec"] == 1800


# ── validate ──────────────────────────────────────────────────────────────────

def test_validate_clean_config_no_warnings():
    assert config.validate(config.DEFAULTS) == []


def test_validate_dictionary_not_dict():
    warns = config.validate({**config.DEFAULTS, "dictionary": ["a", "b"]})
    assert any("dictionary" in w for w in warns)


def test_validate_dictionary_non_string_value():
    warns = config.validate({**config.DEFAULTS, "dictionary": {"hello": 42}})
    assert any("dictionary" in w for w in warns)


def test_validate_extra_fillers_not_list():
    warns = config.validate({**config.DEFAULTS, "extra_fillers": "kinda"})
    assert any("extra_fillers" in w for w in warns)


def test_validate_extra_fillers_non_string_item():
    warns = config.validate({**config.DEFAULTS, "extra_fillers": [1, 2]})
    assert any("extra_fillers" in w for w in warns)


def test_validate_max_recording_sec_negative():
    warns = config.validate({**config.DEFAULTS, "max_recording_sec": -1})
    assert any("max_recording_sec" in w for w in warns)


def test_validate_max_recording_sec_zero_allowed():
    assert config.validate({**config.DEFAULTS, "max_recording_sec": 0}) == []


def test_validate_max_recording_sec_not_number():
    warns = config.validate({**config.DEFAULTS, "max_recording_sec": "ten"})
    assert any("max_recording_sec" in w for w in warns)


def test_validate_paste_mode_invalid():
    warns = config.validate({**config.DEFAULTS, "paste_mode": "magic"})
    assert any("paste_mode" in w for w in warns)


def test_validate_paste_mode_valid():
    assert config.validate({**config.DEFAULTS, "paste_mode": "type"}) == []
    assert config.validate({**config.DEFAULTS, "paste_mode": "clipboard"}) == []


def test_validate_warnings_logged_on_load(tmp_path, caplog):
    import logging
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text('{"extra_fillers": "bad"}', encoding="utf-8")
    with patch("voiceflow.paths.CONFIG_PATH", cfg_path):
        with caplog.at_level(logging.WARNING, logger="voiceflow.config"):
            config.load()
    assert any("extra_fillers" in r.message for r in caplog.records)
