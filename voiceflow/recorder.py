"""Chunked OGG recorder — writes to disk continuously during recording."""
import argparse
import time
from pathlib import Path
from uuid import uuid4

import numpy as np
import sounddevice as sd
import soundfile as sf

from voiceflow import paths

SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
RECORDINGS_DIR = paths.RECORDINGS_DIR

_active: dict[str, dict] = {}


def start_recording() -> str:
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    recording_id = uuid4().hex
    audio_path = RECORDINGS_DIR / f"{recording_id}.ogg"
    sf_file = sf.SoundFile(
        audio_path, mode="w", samplerate=SAMPLE_RATE, channels=CHANNELS,
        format="OGG", subtype="VORBIS",
    )

    def callback(indata: np.ndarray, frames: int, time_info, status) -> None:
        sf_file.write(indata)

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype=DTYPE, callback=callback)
    stream.start()
    _active[recording_id] = {"stream": stream, "file": sf_file, "path": audio_path}
    return recording_id


def stop_recording(recording_id: str) -> Path:
    entry = _active.pop(recording_id)
    entry["stream"].stop()
    entry["stream"].close()
    entry["file"].close()
    return entry["path"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        print("Recording 3 s...")
        rid = start_recording()
        time.sleep(3)
        path = stop_recording(rid)
        size = path.stat().st_size
        print(f"Saved: {path} ({size} bytes)")
        assert size > 0, "audio file empty"
        print("PASS")
