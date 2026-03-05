"""
Utility functions for the Clara AI pipeline.
"""

import json
import os
import logging
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# File I/O helpers
# ---------------------------------------------------------------------------

def read_transcript(path: str) -> str:
    """Read a transcript file and return its text content."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_json(data: dict, path: str, indent: int = 2) -> None:
    """Write a dict as formatted JSON to disk, creating parent dirs if needed."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def read_json(path: str) -> dict:
    """Read JSON from disk and return as dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_text(text: str, path: str) -> None:
    """Write text to a file, creating parent dirs if needed."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


# ---------------------------------------------------------------------------
# Output path helpers
# ---------------------------------------------------------------------------

def get_output_dir(account_id: str, version: str) -> str:
    """Return the output directory for a given account and version."""
    base = Path(__file__).parent.parent / "outputs" / "accounts" / account_id / version
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


def get_account_dir(account_id: str) -> str:
    """Return the account root directory."""
    base = Path(__file__).parent.parent / "outputs" / "accounts" / account_id
    base.mkdir(parents=True, exist_ok=True)
    return str(base)


# ---------------------------------------------------------------------------
# Timestamp helper
# ---------------------------------------------------------------------------

def now_iso() -> str:
    """Return current UTC time in ISO-8601 format."""
    from datetime import timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Deep diff helpers
# ---------------------------------------------------------------------------

def deep_diff(old: dict, new: dict, path: str = "") -> list:
    """
    Recursively diff two dicts. Returns list of change records:
    {"path": ..., "action": "added"|"removed"|"changed", "old": ..., "new": ...}
    """
    changes = []

    all_keys = set(list(old.keys()) + list(new.keys()))
    for key in sorted(all_keys):
        full_path = f"{path}.{key}" if path else key
        if key not in old:
            changes.append({"path": full_path, "action": "added", "old": None, "new": new[key]})
        elif key not in new:
            changes.append({"path": full_path, "action": "removed", "old": old[key], "new": None})
        elif isinstance(old[key], dict) and isinstance(new[key], dict):
            changes.extend(deep_diff(old[key], new[key], full_path))
        elif old[key] != new[key]:
            changes.append({
                "path": full_path,
                "action": "changed",
                "old": old[key],
                "new": new[key],
            })

    return changes
