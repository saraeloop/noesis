"""
Read-only convenience API: summary, events, metrics, list, last, paths
(No imports from loader to avoid cycles.)
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from . import config as _cfg
from .trace.files import (
    EVENTS_FILE,
    SUMMARY_FILE,
    read_events,
    read_summary,
)

# Public read API 

def summary(episode_id: str) -> Dict[str, Any]:
    return read_summary(_run_dir(episode_id))


def events(episode_id: str, *, stream: bool = False):
    run_dir = _run_dir(episode_id)
    if stream:
        def _it() -> Iterator[Dict[str, Any]]:
            for e in read_events(run_dir):
                yield e
        return _it()
    return read_events(run_dir)


def metrics(episode_id: str) -> Dict[str, Any]:
    return summary(episode_id).get("metrics", {})


def list(limit: int = 50, since: str | None = None) -> List[Dict[str, Any]]:
    base = Path(_cfg.get()["runs_dir"])
    rows: List[Dict[str, Any]] = []
    if not base.exists():
        return rows
    for p in base.iterdir():
        if not p.is_dir():
            continue
        sfile = p / SUMMARY_FILE
        if sfile.exists():
            s = read_summary(p)
            rows.append({
                "episode_id": s["episode_id"],
                "task": s.get("task"),
                "started_at": s.get("started_at"),
                "flags": s.get("flags", {}),
                "success": s.get("metrics", {}).get("success"),
            })
    rows.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    return rows[:limit]


def last() -> str | None:
    rows = list(limit=1)
    return rows[0]["episode_id"] if rows else None


def paths(episode_id: str) -> Dict[str, str]:
    d = _run_dir(episode_id)
    return {
        "dir": str(d),
        "events": str(d / EVENTS_FILE),
        "summary": str(d / SUMMARY_FILE),
    }


# Helpers 

def _run_dir(episode_id: str) -> Path:
    return Path(_cfg.get()["runs_dir"]) / episode_id