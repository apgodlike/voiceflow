"""Model download and cache-check for the local Whisper backend."""
import logging
import os
from typing import Callable

logger = logging.getLogger("voiceflow.model_manager")


def recommended_model() -> str:
    """Pick a sensible default local model from CPU core count.

    ``medium`` needs ~4 GB RAM and is only real-time on a capable multi-core
    machine; on a weak CPU it backlogs behind speech and pastes late. ``small.en``
    is fast everywhere. We key off the logical core count: 8+ -> medium.en,
    otherwise small.en. English-only (.en) covers the common case; users pick a
    multilingual model in the wizard if they need other languages.
    """
    cores = os.cpu_count() or 2
    return "distil-medium.en" if cores >= 8 else "distil-small.en"

# ".en" variants are English-only: same size, faster and more accurate than the
# multilingual model of the same size (no 99-language baggage). Multilingual
# models (no suffix) handle any language. "large" is multilingual only.
# "distil-*" are Distil-Whisper: knowledge-distilled, English-only, ~half the
# decoder layers -> 2-4x faster than the full model with near-identical English
# accuracy. The model names below are native faster-whisper aliases, so they
# resolve to these repos and share the same HuggingFace cache.
MODEL_REPOS: dict[str, str] = {
    "tiny":             "Systran/faster-whisper-tiny",
    "tiny.en":          "Systran/faster-whisper-tiny.en",
    "base":             "Systran/faster-whisper-base",
    "base.en":          "Systran/faster-whisper-base.en",
    "small":            "Systran/faster-whisper-small",
    "small.en":         "Systran/faster-whisper-small.en",
    "distil-small.en":  "Systran/faster-distil-whisper-small.en",
    "medium":           "Systran/faster-whisper-medium",
    "medium.en":        "Systran/faster-whisper-medium.en",
    "distil-medium.en": "Systran/faster-distil-whisper-medium.en",
    "large":            "Systran/faster-whisper-large-v3",
    "distil-large-v3":  "Systran/faster-distil-whisper-large-v3",
}

MODEL_SIZES: dict[str, str] = {
    "tiny":             "75 MB",
    "tiny.en":          "75 MB",
    "base":             "145 MB",
    "base.en":          "145 MB",
    "small":            "485 MB",
    "small.en":         "485 MB",
    "distil-small.en":  "330 MB",
    "medium":           "1.5 GB",
    "medium.en":        "1.5 GB",
    "distil-medium.en": "790 MB",
    "large":            "3 GB",
    "distil-large-v3":  "1.5 GB",
}

MODEL_DESCS: dict[str, str] = {
    "tiny":             "Fastest, lower accuracy (multilingual)",
    "tiny.en":          "Fastest, English only",
    "base":             "Fast, basic accuracy (multilingual)",
    "base.en":          "Fast, English only",
    "small":            "Multilingual — for non-English",
    "small.en":         "English, good accuracy",
    "distil-small.en":  "Faster, English — good for lighter PCs",
    "medium":           "Multilingual, high accuracy — slower on CPU",
    "medium.en":        "High accuracy, English",
    "distil-medium.en": "Recommended — fast, English, great accuracy",
    "large":            "Best accuracy, needs 8 GB RAM, slow on CPU (multilingual)",
    "distil-large-v3":  "Max accuracy, English — slow on CPU (~15-20s)",
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


def delete(model_name: str) -> bool:
    """Remove a downloaded model from the HuggingFace cache to free disk space.

    Returns True if something was removed, False if it wasn't cached. Raises on
    a real deletion failure (e.g. file locked because the model is still loaded
    in RAM — callers should drop the in-memory model first).
    """
    repo_id = MODEL_REPOS.get(model_name)
    if not repo_id:
        return False
    from huggingface_hub import scan_cache_dir
    cache = scan_cache_dir()
    hashes = [
        rev.commit_hash
        for repo in cache.repos
        if repo.repo_id == repo_id
        for rev in repo.revisions
    ]
    if not hashes:
        return False
    cache.delete_revisions(*hashes).execute()
    logger.info("Deleted local model '%s' (%s) from cache.", model_name, repo_id)
    return True


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
