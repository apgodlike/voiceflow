"""Tests for queue.py — full round-trip with tmp_path."""
from voiceflow.queue import (
    enqueue,
    list_pending,
    mark_failed,
    mark_success,
    retry_all,
)


def _make_audio(tmp_path, rid):
    audio = tmp_path / f"{rid}.ogg"
    audio.write_bytes(b"fake-audio")
    return audio


def test_enqueue_creates_json(tmp_path):
    queue_dir = tmp_path / "queue"
    job = enqueue("abc123", "/data/recordings/abc123.ogg", queue_dir=queue_dir)
    assert job.recording_id == "abc123"
    assert job.status == "pending"
    assert job.attempts == 0
    assert (queue_dir / "abc123.json").exists()


def test_mark_failed_increments_attempts(tmp_path):
    queue_dir = tmp_path / "queue"
    enqueue("abc123", "/rec/abc123.ogg", queue_dir=queue_dir)
    job = mark_failed("abc123", "network timeout", queue_dir=queue_dir)
    assert job.status == "failed"
    assert job.attempts == 1
    assert "network timeout" in job.last_error


def test_mark_success_deletes_audio_and_queue_file(tmp_path):
    queue_dir = tmp_path / "queue"
    audio = _make_audio(tmp_path, "abc123")
    enqueue("abc123", audio, queue_dir=queue_dir)
    mark_success("abc123", queue_dir=queue_dir)
    assert not (queue_dir / "abc123.json").exists()
    assert not audio.exists(), "audio must be deleted after success"


def test_failure_keeps_audio_for_retry(tmp_path):
    queue_dir = tmp_path / "queue"
    audio = _make_audio(tmp_path, "keepme")
    enqueue("keepme", audio, queue_dir=queue_dir)
    mark_failed("keepme", "boom", queue_dir=queue_dir)
    assert audio.exists(), "audio must survive a failure so it can be retried"
    assert (queue_dir / "keepme.json").exists()


def test_list_pending_returns_all_json(tmp_path):
    queue_dir = tmp_path / "queue"
    enqueue("id1", "/rec/id1.ogg", queue_dir=queue_dir)
    enqueue("id2", "/rec/id2.ogg", queue_dir=queue_dir)
    jobs = list_pending(queue_dir=queue_dir)
    assert {j.recording_id for j in jobs} == {"id1", "id2"}


def test_retry_all_excludes_maxed_attempts(tmp_path):
    queue_dir = tmp_path / "queue"
    enqueue("retry_me", "/rec/r.ogg", queue_dir=queue_dir)
    enqueue("maxed_out", "/rec/m.ogg", queue_dir=queue_dir)
    for _ in range(3):
        mark_failed("maxed_out", "err", queue_dir=queue_dir)
    ids = {j.recording_id for j in retry_all(queue_dir=queue_dir)}
    assert "retry_me" in ids
    assert "maxed_out" not in ids


def test_full_round_trip(tmp_path):
    queue_dir = tmp_path / "queue"
    rid = "full_trip"
    audio = _make_audio(tmp_path, rid)
    enqueue(rid, audio, queue_dir=queue_dir)
    mark_failed(rid, "first fail", queue_dir=queue_dir)
    assert any(j.recording_id == rid for j in retry_all(queue_dir=queue_dir))
    mark_success(rid, queue_dir=queue_dir)
    assert not (queue_dir / f"{rid}.json").exists()
    assert not audio.exists()
