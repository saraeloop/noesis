"""
Summary file helpers.

Handles atomic reads/writes for the per-episode summary snapshot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json
import os
import tempfile

SUMMARY_FILE = "summary.json"

__all__ = ["SUMMARY_FILE", "write_summary", "read_summary"]


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    """Atomic JSON write to prevent partial files on crash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)  # POSIX atomic move


def write_summary(dir_path: Path, summary: Dict[str, Any]) -> None:
    """Write summary.json atomically."""
    _atomic_write_json(dir_path / SUMMARY_FILE, summary)


def read_summary(dir_path: Path) -> Dict[str, Any]:
    """Read summary.json ({} if missing)."""
    p = dir_path / SUMMARY_FILE
    if not p.exists():
        # TODO: log warning if missing during active session
        return {}
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)
