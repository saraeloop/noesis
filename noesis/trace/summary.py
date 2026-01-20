"""
Trace summaries: atomic read/write helpers for per-episode snapshots.

Purpose
-------
Manages the `summary.json` file that captures the final state of each
Noēsis episode. Summaries aggregate metadata, metrics, and direction
flags after execution.

Design
------
- Atomic writes via a temporary file to prevent corruption on crash.
- Human-readable JSON with stable key ordering.
- Always safe to read; missing files yield `{}` instead of errors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json

from noesis.runtime.serialization import atomic_write_json
from noesis.domain.artifacts.immutability import ArtifactWriteMode
from noesis.runtime.artifacts.immutability import default_artifact_guard

SUMMARY_FILE = "summary.json"

__all__ = ["SUMMARY_FILE", "write_summary", "read_summary"]



# Internal Utilities

def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON atomically to avoid partial writes on crash."""
    atomic_write_json(path, data)



# Public API

def _prune_summary(summary: Dict[str, Any]) -> Dict[str, Any]:
    """Remove empty optional sections to keep artifacts tidy."""
    for key in ("hints", "risk_forecast"):
        if not summary.get(key):
            summary.pop(key, None)

    if not summary.get("answer"):
        summary.pop("answer", None)

    metrics = summary.get("metrics")
    if isinstance(metrics, dict):
        experimental = metrics.get("experimental")
        if not experimental:
            metrics.pop("experimental", None)
    return summary


def write_summary(dir_path: Path, summary: Dict[str, Any]) -> None:
    """Atomically write `summary.json` under the given episode directory."""
    default_artifact_guard().ensure_write_allowed(
        episode_dir=dir_path,
        artifact=SUMMARY_FILE,
        mode=ArtifactWriteMode.OVERWRITE,
    )
    _atomic_write_json(dir_path / SUMMARY_FILE, _prune_summary(summary))


def read_summary(dir_path: Path) -> Dict[str, Any]:
    """Read `summary.json`, returning an empty dict if missing."""
    p = dir_path / SUMMARY_FILE
    if not p.exists():
        # Future: log warning if missing during active session
        return {}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)
