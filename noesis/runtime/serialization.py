"""
Canonical JSON serialization utilities for deterministic artifacts.

These helpers keep JSON output stable across Python versions and platforms by:
- sorting keys
- using compact separators
- disabling ASCII escaping
- normalising trailing newlines

I/O stays here in the infrastructure layer; callers should inject values and keep
domain logic pure.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
import json
import os
import tempfile

from noesis._fs import fsync_dir

JsonDefault = Callable[[Any], Any]

__all__ = ["canonical_dumps", "atomic_write_json", "atomic_write_text"]


def canonical_dumps(value: Any, *, default: JsonDefault | None = None) -> str:
    """
    Render a JSON string with stable ordering and formatting.

    - ensure_ascii=False to preserve UTF-8
    - sort_keys=True for deterministic key order
    - separators=(",", ":") for compact, consistent output
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=default,
    )


def atomic_write_json(path: Path, value: Any, *, default: JsonDefault | None = None) -> None:
    """Atomically write canonical JSON with a single trailing newline."""
    payload = canonical_dumps(value, default=default)
    atomic_write_text(path, payload)


def atomic_write_text(path: Path, payload: str) -> None:
    """
    Atomically write text, normalising a single trailing newline.

    This keeps manifest/state/summary files byte-identical across runs.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _ensure_trailing_newline(payload)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as tmp:
        tmp.write(normalized)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)
    fsync_dir(path.parent)


def _ensure_trailing_newline(payload: str) -> str:
    if payload.endswith("\n"):
        # collapse multiple trailing newlines down to one
        return payload.rstrip("\n") + "\n"
    return payload + "\n"
