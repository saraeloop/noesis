"""
Introspection and trace I/O for Noēsis.

Provides a stable, read-only interface to past execution artifacts:
    • summary()  →  load episode summary JSON
    • events()   →  iterate or stream structured event logs
    • metrics()  →  extract computed metrics from summaries
    • list_runs() → enumerate prior runs with brief metadata
    • last()     →  return the most recent episode ID
    • paths()    →  resolve canonical file locations

Design goals:
    - Immutable by design (read-only surface)
    - Aligned with trace schema for easy analysis
    - Serves as the bridge between runtime episodes and the insight layer
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from .trace.events import EVENTS_FILE, read_events
from .trace.summary import SUMMARY_FILE, read_summary
from .runtime.config_provider import RuntimeContainer, get_config_snapshot


def _config_snapshot(container: RuntimeContainer | None):
    if container is None:
        return get_config_snapshot()
    config_port = container.require("config", getattr(container.config_port, "__api_version__", "config/1.0-rc1"))
    return config_port.get()


# Public Read API

def summary(episode_id: str, *, container: RuntimeContainer | None = None) -> Dict[str, Any]:
    """Return the parsed summary JSON for a given episode."""
    return read_summary(_run_dir(episode_id, container=container))


def events(episode_id: str, *, stream: bool = False, container: RuntimeContainer | None = None):
    """
    Load event logs for a given episode.

    If `stream=True`, returns an iterator for on-the-fly consumption.
    """
    run_dir = _run_dir(episode_id, container=container)
    if stream:
        def _it() -> Iterator[Dict[str, Any]]:
            for e in read_events(run_dir):
                yield e
        return _it()
    return read_events(run_dir)


def metrics(episode_id: str) -> Dict[str, Any]:
    """Extract only the metrics section from an episode summary."""
    return summary(episode_id).get("metrics", {})


def list_runs(
    limit: int = 50,
    since: Optional[str] = None,
    *,
    container: RuntimeContainer | None = None,
) -> List[Dict[str, Any]]:
    """
    Return a list of recent runs with brief metadata.

    Each entry includes:
        - episode_id
        - task
        - started_at
        - flags
        - success metric (if available)
    """
    base = _config_snapshot(container).runs_dir
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


def last(*, container: RuntimeContainer | None = None) -> Optional[str]:
    """Return the ID of the most recent episode, if any."""
    rows = list_runs(limit=1, container=container)
    return rows[0]["episode_id"] if rows else None


def paths(episode_id: str, *, container: RuntimeContainer | None = None) -> Dict[str, str]:
    """Return canonical file paths for the given episode."""
    d = _run_dir(episode_id, container=container)
    return {
        "dir": str(d),
        "events": str(d / EVENTS_FILE),
        "summary": str(d / SUMMARY_FILE),
    }



# Internal Helpers

def _run_dir(episode_id: str, *, container: RuntimeContainer | None = None) -> Path:
    """Resolve the filesystem directory for a given episode."""
    return _config_snapshot(container).runs_dir / episode_id
