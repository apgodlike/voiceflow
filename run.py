"""Frozen-app entry point — keeps package imports working under PyInstaller."""
import os
import sys

# A windowed PyInstaller build (console=False) has no console, so sys.stdout and
# sys.stderr are None. Any library that writes to them — huggingface_hub/tqdm
# download progress bars, ctranslate2/faster-whisper chatter, stray prints —
# raises "'NoneType' object has no attribute 'write'". That crashed the local
# model download (medium/large) and stalled model load. Redirect the missing
# streams to the null device before importing anything that might write.
if sys.stdout is None or sys.stderr is None:
    _devnull = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = _devnull
    if sys.stderr is None:
        sys.stderr = _devnull
    # tqdm on a null stream is harmless but pointless — silence HF progress bars.
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

from voiceflow.main import main

if __name__ == "__main__":
    main()
