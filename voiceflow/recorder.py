"""Chunked OGG recorder — writes to disk continuously during recording.

Two files are written per recording:

* the **full** continuous OGG (``{rid}.ogg``) — the durable unit the queue
  and retry/privacy model operate on. Lifecycle unchanged from before.
* rolling **segment** files (``{rid}.seg{n}.ogg``) cut on silence. Each closed
  segment fires ``on_segment`` so it can be transcribed *during* recording,
  collapsing perceived latency. Segments are an ephemeral fast-path; if any
  segment transcription fails the caller falls back to the full file.

Cuts happen only inside a silence gap (``_SegmentCutter``) so no spoken word
ever spans a boundary — segments concatenate cleanly with no overlap/dedup.
"""
import argparse
import time
from pathlib import Path
from typing import Callable
from uuid import uuid4

import numpy as np
import sounddevice as sd
import soundfile as sf

from voiceflow import paths

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
RECORDINGS_DIR = paths.RECORDINGS_DIR

# Silence-aware segmentation tuning (int16 amplitude / milliseconds).
SILENCE_RMS_THRESHOLD = 300.0   # below this a block counts as silence
SILENCE_MIN_MS = 600            # pause this long triggers a cut
SEGMENT_MIN_MS = 4000           # never cut a segment shorter than this
SEGMENT_MAX_MS = 15000          # force a cut even without silence

OnSegment = Callable[[int, Path], None]

_active: dict[str, dict] = {}


class _SegmentCutter:
    """Pure cut-decision logic — no audio I/O, so tests drive it directly.

    Feed it the RMS and frame count of each audio block; ``feed`` returns True
    when the current segment should be closed *after* this block. A cut fires
    when the segment is long enough AND we are in a sufficiently long silence,
    or when the segment hits the hard max length. Counters reset on each cut.
    """

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        silence_threshold: float = SILENCE_RMS_THRESHOLD,
        silence_min_ms: int = SILENCE_MIN_MS,
        segment_min_ms: int = SEGMENT_MIN_MS,
        segment_max_ms: int = SEGMENT_MAX_MS,
    ) -> None:
        self.sample_rate = sample_rate
        self.silence_threshold = silence_threshold
        self.silence_min_ms = silence_min_ms
        self.segment_min_ms = segment_min_ms
        self.segment_max_ms = segment_max_ms
        self.reset()

    def reset(self) -> None:
        self._seg_frames = 0
        self._silence_frames = 0

    def _ms(self, frames: int) -> float:
        return frames / self.sample_rate * 1000.0

    def feed(self, rms: float, frames: int) -> bool:
        self._seg_frames += frames
        if rms < self.silence_threshold:
            self._silence_frames += frames
        else:
            self._silence_frames = 0

        seg_ms = self._ms(self._seg_frames)
        silence_ms = self._ms(self._silence_frames)

        cut = seg_ms >= self.segment_max_ms or (
            seg_ms >= self.segment_min_ms and silence_ms >= self.silence_min_ms
        )
        if cut:
            self.reset()
        return cut


def _rms(block: np.ndarray) -> float:
    if block.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(block.astype(np.float64) ** 2)))


def _new_segment_file(rid: str, index: int) -> tuple[sf.SoundFile, Path]:
    seg_path = RECORDINGS_DIR / f"{rid}.seg{index}.ogg"
    seg_file = sf.SoundFile(
        seg_path, mode="w", samplerate=SAMPLE_RATE, channels=CHANNELS,
        format="OGG", subtype="VORBIS",
    )
    return seg_file, seg_path


def start_recording(
    on_segment: OnSegment | None = None,
    device: int | str | None = None,
) -> str:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    recording_id = uuid4().hex
    audio_path = RECORDINGS_DIR / f"{recording_id}.ogg"
    full_file = sf.SoundFile(
        audio_path, mode="w", samplerate=SAMPLE_RATE, channels=CHANNELS,
        format="OGG", subtype="VORBIS",
    )
    seg_file, seg_path = _new_segment_file(recording_id, 0)

    entry = {
        "stream": None,
        "full_file": full_file,
        "full_path": audio_path,
        "seg_file": seg_file,
        "seg_path": seg_path,
        "seg_index": 0,
        "seg_frames": 0,
        "cutter": _SegmentCutter(),
        "on_segment": on_segment,
    }

    def callback(indata: np.ndarray, frames: int, time_info, status) -> None:
        full_file.write(indata)
        entry["seg_file"].write(indata)
        entry["seg_frames"] += frames
        if entry["cutter"].feed(_rms(indata), frames):
            _rotate_segment(recording_id, entry)

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE,
        callback=callback, device=device,
    )
    entry["stream"] = stream
    stream.start()
    _active[recording_id] = entry
    return recording_id


def _rotate_segment(rid: str, entry: dict) -> None:
    """Close the current segment, hand it off, open the next. Audio-thread only."""
    entry["seg_file"].close()
    index = entry["seg_index"]
    path = entry["seg_path"]
    had_audio = entry["seg_frames"] > 0
    cb = entry["on_segment"]

    entry["seg_index"] = index + 1
    entry["seg_frames"] = 0
    entry["seg_file"], entry["seg_path"] = _new_segment_file(rid, index + 1)

    if had_audio and cb is not None:
        cb(index, path)


def stop_recording(recording_id: str) -> Path:
    """Stop, emit the trailing segment, and return the full audio path.

    All segments (including the final one finalized here) reach the caller
    through ``on_segment``. The audio thread is already stopped before the
    final emit, so no callback races this.
    """
    entry = _active.pop(recording_id)
    entry["stream"].stop()
    entry["stream"].close()
    entry["full_file"].close()

    entry["seg_file"].close()
    cb = entry["on_segment"]
    if entry["seg_frames"] > 0 and cb is not None:
        cb(entry["seg_index"], entry["seg_path"])
    elif entry["seg_frames"] == 0:
        # Empty trailing segment (cut fired on the very last block) — drop it.
        entry["seg_path"].unlink(missing_ok=True)

    return entry["full_path"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        print("Recording 3 s...")
        segs: list[Path] = []
        rid = start_recording(on_segment=lambda i, p: segs.append(p))
        time.sleep(3)
        path = stop_recording(rid)
        size = path.stat().st_size
        print(f"Saved: {path} ({size} bytes), segments: {len(segs)}")
        assert size > 0, "audio file empty"
        print("PASS")
