"""
Read-only convenience API for inspecting past episodes.

Functions:
    summary()  →  Load episode summary JSON
    events()   →  Load or stream event logs
    metrics()  →  Extract computed metrics
    list_runs() → List prior runs with brief metadata
    last()     →  Get most recent episode ID
    paths()    →  Canonical file paths for an episode
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from . import config as _cfg
from .trace.files import EVENTS_FILE, SUMMARY_FILE, read_events, read_summary



# Public Read API

def summary(episode_id: str) -> Dict[str, Any]:
    """Return the parsed summary JSON for a given episode."""
    return read_summary(_run_dir(episode_id))


def events(episode_id: str, *, stream: bool = False):
    """
    Load event logs for a given episode.

    If `stream=True`, returns an iterator for on-the-fly consumption.
    """
    run_dir = _run_dir(episode_id)
    if stream:
        def _it() -> Iterator[Dict[str, Any]]:
            for e in read_events(run_dir):
                yield e
        return _it()
    return read_events(run_dir)


def metrics(episode_id: str) -> Dict[str, Any]:
    """Extract only the metrics section from an episode summary."""
    return summary(episode_id).get("metrics", {})


def list_runs(limit: int = 50, since: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Return a list of recent runs with brief metadata.

    Each entry includes:
        - episode_id
        - task
        - started_at
        - flags
        - success metric (if available)
    """
    base = Path(_cfg.get()["runs_dir"])
    rows: List[Dict[str, Any]] = []

    if not base.exists():
        return rows

    for p in base.iterdir():
        if not p.is_dir():
            continue
        sfile = p / SUMMARY_FILE
        if not sfile.exists():
            continue

        s = read_summary(p)
        rows.append({
            "episode_id": s.get("episode_id"),
            "task": s.get("task"),
            "started_at": s.get("started_at"),
            "flags": s.get("flags", {}),
            "success": s.get("metrics", {}).get("success"),
        })

    rows.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    return rows[:limit]


def last() -> Optional[str]:
    """Return the ID of the most recent episode, if any."""
    rows = list_runs(limit=1)
    return rows[0]["episode_id"] if rows else None


def paths(episode_id: str) -> Dict[str, str]:
    """Return canonical file paths for the given episode."""
    d = _run_dir(episode_id)
    return {
        "dir": str(d),
        "events": str(d / EVENTS_FILE),
        "summary": str(d / SUMMARY_FILE),
    }



# Internal Helpers

def _run_dir(episode_id: str) -> Path:
    """Resolve the filesystem directory for a given episode."""
    return Path(_cfg.get()["runs_dir"]) / episode_id