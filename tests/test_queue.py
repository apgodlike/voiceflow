"""Tests for queue.py — full round-trip with tmp_path."""
import sqlite3
from pathlib import Path

import pytest

from voiceflow.queue import (
    Job,
    enqueue,
    list_pending,
    mark_failed,
    mark_success,
    retry_all,
)


def test_enqueue_creates_json(tmp_path):
    queue_dir = tmp_path / "queue"
    job = enqueue("abc123", "/data/recordings/abc123.wav", queue_dir=queue_dir)
    assert job.recording_id == "abc123"
    assert job.status == "pending"
    assert job.attempts == 0
    assert (queue_dir / "abc123.json").exists()


def test_mark_failed_increments_attempts(tmp_path):
    queue_dir = tmp_path / "queue"
    enqueue("abc123", "/rec/abc123.wav", queue_dir=queue_dir)
    job = mark_failed("abc123", "network timeout", queue_dir=queue_dir)
    assert job.status == "failed"
    assert job.attempts == 1
    assert "network timeout" in job.last_error


def test_mark_success_removes_queue_file_and_writes_db(tmp_path):
    queue_dir = tmp_path / "queue"
    db_path = tmp_path / "history.sqlite"
    enqueue("abc123", "/rec/abc123.wav", queue_dir=queue_dir)
    mark_success("abc123", "raw text", "Cleaned text.", queue_dir=queue_dir, db_path=db_path)
    assert not (queue_dir / "abc123.json").exists()
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT raw_text, cleaned_text FROM history WHERE id=?", ("abc123",)).fetchone()
    assert row == ("raw text", "Cleaned text.")


def test_list_pending_returns_all_json(tmp_path):
    queue_dir = tmp_path / "queue"
    enqueue("id1", "/rec/id1.wav", queue_dir=queue_dir)
    enqueue("id2", "/rec/id2.wav", queue_dir=queue_dir)
    jobs = list_pending(queue_dir=queue_dir)
    assert {j.recording_id for j in jobs} == {"id1", "id2"}


def test_retry_all_excludes_maxed_attempts(tmp_path):
    queue_dir = tmp_path / "queue"
    enqueue("retry_me", "/rec/r.wav", queue_dir=queue_dir)
    enqueue("maxed_out", "/rec/m.wav", queue_dir=queue_dir)
    for _ in range(3):
        mark_failed("maxed_out", "err", queue_dir=queue_dir)
    retryable = list(retry_all(queue_dir=queue_dir))
    ids = {j.recording_id for j in retryable}
    assert "retry_me" in ids
    assert "maxed_out" not in ids


def test_full_round_trip(tmp_path):
    queue_dir = tmp_path / "queue"
    db_path = tmp_path / "history.sqlite"
    rid = "full_trip"
    enqueue(rid, "/rec/full.wav", queue_dir=queue_dir)
    mark_failed(rid, "first fail", queue_dir=queue_dir)
    retryable = list(retry_all(queue_dir=queue_dir))
    assert any(j.recording_id == rid for j in retryable)
    mark_success(rid, "hello world", "Hello world.", queue_dir=queue_dir, db_path=db_path)
    assert not (queue_dir / f"{rid}.json").exists()
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT count(*) FROM history WHERE id=?", (rid,)).fetchone()[0]
    assert count == 1
