"""Optional LLM cleanup pass — turn rough dictation into clean prose.

Opt-in (``ai_cleanup`` off by default). Runs *after* the rule-based ``cleaner``.
Two providers:

* ``ollama`` — local, private, offline (POST to http://localhost:11434). Default,
  matches VoiceFlow's local-first stance.
* ``openai`` — reuses the user's OpenAI key for those who prefer the cloud.

Design rule: **fail open.** Any error (no Ollama running, timeout, bad key) returns
the original cleaned text — an AI-cleanup hiccup must never lose a dictation.
"""
import logging
import os
from typing import Any

logger = logging.getLogger("voiceflow.ai_cleanup")

_OLLAMA_URL = "http://localhost:11434/api/generate"
_TIMEOUT_SEC = 12

_DEFAULT_PROMPT = (
    "You clean up speech-to-text transcripts. Fix grammar, punctuation, "
    "capitalization, and obvious dictation errors. Do NOT add, remove, or change "
    "the meaning, and do NOT answer or comment on the content. Return ONLY the "
    "cleaned text, nothing else.\n\nTranscript:\n{text}"
)


def _prompt(cfg: dict[str, Any], text: str) -> str:
    template = (cfg.get("ai_cleanup_prompt") or "").strip() or _DEFAULT_PROMPT
    if "{text}" in template:
        return template.format(text=text)
    return f"{template}\n\nTranscript:\n{text}"


def _via_ollama(cfg: dict[str, Any], text: str) -> str:
    import requests
    model = cfg.get("ai_cleanup_model") or "llama3.2"
    resp = requests.post(
        _OLLAMA_URL,
        json={"model": model, "prompt": _prompt(cfg, text), "stream": False},
        timeout=_TIMEOUT_SEC,
    )
    resp.raise_for_status()
    return (resp.json().get("response") or "").strip()


def _via_openai(cfg: dict[str, Any], text: str) -> str:
    from openai import OpenAI
    key = cfg.get("openai_api_key") or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OpenAI cleanup selected but no API key set")
    model = cfg.get("ai_cleanup_model") or "gpt-4o-mini"
    client = OpenAI(api_key=key)
    out = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": _prompt(cfg, text)}],
        temperature=0,
        timeout=_TIMEOUT_SEC,
    )
    return (out.choices[0].message.content or "").strip()


def refine(text: str, cfg: dict[str, Any]) -> str:
    """Return an LLM-cleaned version of ``text``; the original on any failure."""
    if not cfg.get("ai_cleanup") or not text.strip():
        return text
    provider = cfg.get("ai_cleanup_provider", "ollama")
    try:
        if provider == "openai":
            cleaned = _via_openai(cfg, text)
        else:
            cleaned = _via_ollama(cfg, text)
        # Guard against an empty or junk response — never paste less than we had.
        if cleaned and len(cleaned) >= len(text) * 0.4:
            return cleaned
        logger.warning("AI cleanup returned a suspicious result; keeping original.")
        return text
    except Exception as exc:
        logger.warning("AI cleanup (%s) failed, keeping original: %s", provider, exc)
        return text
