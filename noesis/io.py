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
from .runtime.artifacts.manifest import MANIFEST_FILE_NAME, compute_sha256
from .context import RuntimeContext, get_config_snapshot


def _config_snapshot(context: RuntimeContext | None):
    if context is None:
        return get_config_snapshot()
    config_port = context.require("config", getattr(context.config_port, "__api_version__", "config/1.0-rc1"))
    return config_port.get()


# Public Read API

def summary(episode_id: str, *, context: RuntimeContext | None = None) -> Dict[str, Any]:
    """Return the parsed summary JSON for a given episode."""
    return read_summary(_run_dir(episode_id, context=context))


def events(episode_id: str, *, stream: bool = False, context: RuntimeContext | None = None):
    """
    Load event logs for a given episode.

    If `stream=True`, returns an iterator for on-the-fly consumption.
    """
    run_dir = _run_dir(episode_id, context=context)
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
    context: RuntimeContext | None = None,
    strict_manifest: bool = False,
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
    base = _config_snapshot(context).runs_dir
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
        manifest_meta = s.get("manifest") or {}
        manifest_status = None
        if strict_manifest:
            manifest_status = _verify_manifest(p, manifest_meta)
            if manifest_meta is not None and manifest_status is not None:
                manifest_meta["status"] = manifest_status
        rows.append({
            "episode_id": s.get("episode_id"),
            "task": s.get("task"),
            "started_at": s.get("started_at"),
            "flags": s.get("flags", {}),
            "success": s.get("metrics", {}).get("success"),
            "veto_count": s.get("metrics", {}).get("veto_count"),
            "duration_sec": s.get("duration_sec"),
            "status": s.get("status"),
            "outcome": s.get("outcome"),
            "manifest": manifest_meta,
            "manifest_status": manifest_status,
        })

    rows.sort(key=lambda r: r.get("started_at") or "", reverse=True)
    return rows[:limit]


def last(*, context: RuntimeContext | None = None) -> Optional[str]:
    """Return the ID of the most recent episode, if any."""
    rows = list_runs(limit=1, context=context)
    return rows[0]["episode_id"] if rows else None


def paths(episode_id: str, *, context: RuntimeContext | None = None) -> Dict[str, str]:
    """Return canonical file paths for the given episode."""
    d = _run_dir(episode_id, context=context)
    return {
        "dir": str(d),
        "events": str(d / EVENTS_FILE),
        "summary": str(d / SUMMARY_FILE),
        "manifest": str(d / MANIFEST_FILE_NAME),
    }



# Internal Helpers

def _run_dir(episode_id: str, *, context: RuntimeContext | None = None) -> Path:
    """Resolve the filesystem directory for a given episode."""
    return _config_snapshot(context).runs_dir / episode_id


def _verify_manifest(run_dir: Path, manifest_meta: Dict[str, Any]) -> str | None:
    path = manifest_meta.get("path") or MANIFEST_FILE_NAME
    sha = manifest_meta.get("sha256")
    manifest_path = run_dir / path
    if not manifest_path.exists():
        return "missing"
    actual = compute_sha256(manifest_path)
    if sha and actual != sha:
        return "mismatch"
    return "ok"
