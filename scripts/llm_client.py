"""
LLM integration module — supports multiple zero-cost backends.

Backends (in priority order):
  1. groq     — Groq Cloud free tier (requires GROQ_API_KEY env var)
  2. ollama   — local Ollama instance (requires Ollama running locally)
  3. rule_based — pure regex/rule extraction (always available, no LLM needed)

Set LLM_BACKEND env var to choose, or let the module auto-detect.
"""

import os
import json
import re
from typing import Optional
from scripts.utils import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Backend detection
# ---------------------------------------------------------------------------

def _detect_backend() -> str:
    explicit = os.environ.get("LLM_BACKEND", "").lower()
    if explicit in ("groq", "ollama", "rule_based"):
        return explicit

    # Auto-detect: prefer Groq if key is present
    if os.environ.get("GROQ_API_KEY"):
        return "groq"

    # Try Ollama if URL is set or default port responds
    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    try:
        import urllib.request
        urllib.request.urlopen(f"{ollama_url}/api/tags", timeout=2)
        return "ollama"
    except Exception:
        pass

    return "rule_based"


BACKEND = _detect_backend()
logger.info("LLM backend selected: %s", BACKEND)


# ---------------------------------------------------------------------------
# Groq backend
# ---------------------------------------------------------------------------

def _call_groq(system_prompt: str, user_prompt: str) -> str:
    """Call Groq API with the given prompts. Returns the assistant response text."""
    try:
        from groq import Groq  # type: ignore
    except ImportError:
        raise RuntimeError("groq package not installed — run: pip install groq")

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable is not set")

    client = Groq(api_key=api_key)
    model = os.environ.get("GROQ_MODEL", "llama3-8b-8192")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=4096,
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Ollama backend
# ---------------------------------------------------------------------------

def _call_ollama(system_prompt: str, user_prompt: str) -> str:
    """Call local Ollama instance."""
    import urllib.request
    import urllib.error

    ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3")

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{ollama_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["message"]["content"]


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def call_llm(system_prompt: str, user_prompt: str, backend: Optional[str] = None) -> str:
    """
    Call the configured LLM backend.  Falls back to rule_based if LLM fails.

    Returns the raw text response from the model (caller is responsible for
    parsing JSON from it).
    """
    b = backend or BACKEND

    if b == "groq":
        try:
            return _call_groq(system_prompt, user_prompt)
        except Exception as exc:
            logger.warning("Groq call failed (%s) — falling back to rule_based", exc)
            return "RULE_BASED_FALLBACK"

    if b == "ollama":
        try:
            return _call_ollama(system_prompt, user_prompt)
        except Exception as exc:
            logger.warning("Ollama call failed (%s) — falling back to rule_based", exc)
            return "RULE_BASED_FALLBACK"

    return "RULE_BASED_FALLBACK"


def is_llm_available() -> bool:
    """Return True if an LLM backend other than rule_based is usable."""
    return BACKEND in ("groq", "ollama")
