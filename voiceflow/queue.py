"""Disk-backed retry queue.

A job's audio file is the source of truth until it is transcribed and pasted
successfully. On success both the audio and the queue entry are deleted (no
transcript is persisted — see privacy design). On failure the audio is kept so
the job can be retried, automatically up to ``MAX_ATTEMPTS`` and then manually.
"""
import argparse
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from voiceflow import paths

logger = logging.getLogger("voiceflow.queue")

QUEUE_DIR = paths.QUEUE_DIR
MAX_ATTEMPTS = 3


@dataclass
class Job:
    recording_id: str
    audio_path: str
    status: str = "pending"
    attempts: int = 0
    last_error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


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


def enqueue(recording_id: str, audio_path: str | Path, queue_dir: Path = QUEUE_DIR) -> Job:
    job = Job(recording_id=recording_id, audio_path=str(audio_path))
    _write_job(job, queue_dir)
    return job


def mark_failed(recording_id: str, error: str, queue_dir: Path = QUEUE_DIR) -> Job:
    job = _read_job(recording_id, queue_dir)
    job.status = "failed"
    job.attempts += 1
    job.last_error = error
    _write_job(job, queue_dir)
    return job


def mark_success(recording_id: str, queue_dir: Path = QUEUE_DIR) -> None:
    """Delete the audio file and the queue entry — nothing is persisted."""
    job = _read_job(recording_id, queue_dir)
    Path(job.audio_path).unlink(missing_ok=True)
    _queue_path(recording_id, queue_dir).unlink(missing_ok=True)


def list_pending(queue_dir: Path = QUEUE_DIR) -> list[Job]:
    if not queue_dir.exists():
        return []
    jobs = []
    for p in queue_dir.glob("*.json"):
        try:
            jobs.append(Job(**json.loads(p.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, TypeError, OSError) as exc:
            logger.warning("Skipping unreadable queue file %s: %s", p.name, exc)
    return jobs


def retry_all(queue_dir: Path = QUEUE_DIR) -> Iterator[Job]:
    for job in list_pending(queue_dir):
        if job.attempts < MAX_ATTEMPTS:
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
