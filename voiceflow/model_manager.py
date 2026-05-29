"""Model download and cache-check for the local Whisper backend."""
import logging
from typing import Callable

logger = logging.getLogger("voiceflow.model_manager")

MODEL_REPOS: dict[str, str] = {
    "tiny":   "Systran/faster-whisper-tiny",
    "base":   "Systran/faster-whisper-base",
    "small":  "Systran/faster-whisper-small",
    "medium": "Systran/faster-whisper-medium",
    "large":  "Systran/faster-whisper-large-v3",
}

MODEL_SIZES: dict[str, str] = {
    "tiny":   "75 MB",
    "base":   "145 MB",
    "small":  "485 MB",
    "medium": "1.5 GB",
    "large":  "3 GB",
}

MODEL_DESCS: dict[str, str] = {
    "tiny":   "Fastest, lower accuracy",
    "base":   "Good balance (recommended)",
    "small":  "Better accuracy",
    "medium": "High accuracy, needs 4 GB RAM",
    "large":  "Best accuracy, needs 8 GB RAM",
}


def is_cached(model_name: str) -> bool:
    """Return True if the model is already in the HuggingFace cache."""
    try:
        from huggingface_hub import try_to_load_from_cache
        result = try_to_load_from_cache(
            repo_id=MODEL_REPOS.get(model_name, ""),
            filename="model.bin",
        )
        return isinstance(result, str)
    except Exception:
        return False


def download(model_name: str, on_progress: Callable[[int, int], None]) -> None:
    """Download all model files from HuggingFace.

    Calls on_progress(done, total) after each file completes.
    Files already in cache are skipped instantly.
    Raises on network or auth failure.
    """
    from huggingface_hub import hf_hub_download, list_repo_files
    repo_id = MODEL_REPOS[model_name]
    files = list(list_repo_files(repo_id))
    total = len(files)
    for i, filename in enumerate(files):
        hf_hub_download(repo_id=repo_id, filename=filename)
        on_progress(i + 1, total)
