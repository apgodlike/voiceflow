"""Disk-backed retry queue + sqlite history."""
import argparse
import json
import os
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

BASE_DIR = Path(__file__).parent.parent / "data"
QUEUE_DIR = BASE_DIR / "queue"
DB_PATH = BASE_DIR / "history.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id TEXT PRIMARY KEY,
    raw_text TEXT NOT NULL,
    cleaned_text TEXT NOT NULL,
    wav_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


@dataclass
class Job:
    recording_id: str
    wav_path: str
    status: str = "pending"
    attempts: int = 0
    last_error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def _init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(_SCHEMA)


def _queue_path(recording_id: str, queue_dir: Path = QUEUE_DIR) -> Path:
    return queue_dir / f"{recording_id}.json"


def _write_job(job: Job, queue_dir: Path = QUEUE_DIR) -> None:
    queue_dir.mkdir(parents=True, exist_ok=True)
    target = _queue_path(job.recording_id, queue_dir)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(job)), encoding="utf-8")
    os.replace(tmp, target)


def _read_job(recording_id: str, queue_dir: Path = QUEUE_DIR) -> Job:
    data = json.loads(_queue_path(recording_id, queue_dir).read_text(encoding="utf-8"))
    return Job(**data)


def enqueue(recording_id: str, wav_path: str | Path, queue_dir: Path = QUEUE_DIR) -> Job:
    job = Job(recording_id=recording_id, wav_path=str(wav_path))
    _write_job(job, queue_dir)
    return job


def mark_failed(recording_id: str, error: str, queue_dir: Path = QUEUE_DIR) -> Job:
    job = _read_job(recording_id, queue_dir)
    job.status = "failed"
    job.attempts += 1
    job.last_error = error
    _write_job(job, queue_dir)
    return job


def mark_success(
    recording_id: str,
    raw: str,
    cleaned: str,
    queue_dir: Path = QUEUE_DIR,
    db_path: Path = DB_PATH,
) -> None:
    job = _read_job(recording_id, queue_dir)
    _init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO history (id, raw_text, cleaned_text, wav_path, created_at) VALUES (?,?,?,?,?)",
            (job.recording_id, raw, cleaned, job.wav_path, job.created_at),
        )
    _queue_path(recording_id, queue_dir).unlink()


def list_pending(queue_dir: Path = QUEUE_DIR) -> list[Job]:
    if not queue_dir.exists():
        return []
    jobs = []
    for p in queue_dir.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            jobs.append(Job(**data))
        except Exception:
            pass
    return jobs


def retry_all(queue_dir: Path = QUEUE_DIR) -> Iterator[Job]:
    for job in list_pending(queue_dir):
        if job.attempts < 3:
            yield job


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--retry-all", action="store_true")
    args = parser.parse_args()
    if args.list:
        for j in list_pending():
            print(f"{j.recording_id}  status={j.status}  attempts={j.attempts}  error={j.last_error!r}")
    if args.retry_all:
        for j in retry_all():
            print(f"Would retry: {j.recording_id}")
