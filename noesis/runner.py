"""
Facade exposing the public API:
    run, summary, events, metrics, list, last, set, paths
Internals (LangGraph wiring, tools, IO) can evolve without breaking this API.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Iterator, List, Optional
from datetime import datetime, timezone

from . import config as _cfg
from .state import new_episode_id, EpisodeSummary
from .trace import read_summary, write_summary, read_events, write_event, EVENTS_FILE, SUMMARY_FILE
from .eval import compute_metrics
from .intuition import generate_hints, forecast_risks

SCHEMA_VERSION = "1.0.0"

# Public API 

def set(**overrides: Any) -> None:
    """Update global configuration (paths, agents file, tasks file, timeout)."""
    _cfg.set(**overrides)

def run(task: str, *, seed: int = 0, intuition: bool = True, tags: Dict[str, Any] | None = None) -> str:
    """
    Execute one episode and persist outputs under runs/<episode_id>/.
    Returns the episode_id.
    """
    cfg = _cfg.get()
    episode_id = new_episode_id(seed)
    run_dir = Path(cfg["runs_dir"]) / episode_id
    started_at = datetime.now(timezone.utc).isoformat()

    # Intuition layer (noop for now)
    hints = generate_hints(task)
    risks = forecast_risks(task, agents=None)  # plug agents later

    # Minimal summary scaffold
    summ = EpisodeSummary(
        schema_version=SCHEMA_VERSION,
        episode_id=episode_id,
        task=task,
        seed=seed,
        started_at=started_at,
        flags={"intuition": bool(intuition)},
        agents_config_hash="sha256:TODO",
        hints=hints if intuition else [],
        risk_forecast=risks if intuition else [],
        answer={},
        metrics={},
        tags=tags or {},
    ).__dict__

    # Write an initial “start” event (placeholder)
    write_event(run_dir, {
        "ts": started_at,
        "episode_id": episode_id,
        "agent_id": "system",
        "phase": "start",
        "message": f"episode started: task={task}",
        "payload": {},
        "evidence_ids": [],
    })

    # TODO: run the real graph here and stream events…

    # Finalize metrics (using placeholder pure fn)
    ev = read_events(run_dir)
    summ["metrics"] = compute_metrics(summ, ev)

    # Persist summary
    write_summary(run_dir, summ)
    return episode_id

def summary(episode_id: str) -> Dict[str, Any]:
    """Load summary.json for the given episode."""
    return read_summary(_run_dir(episode_id))

def events(episode_id: str, *, stream: bool = False):
    """
    Load or stream events for the given episode.
    If stream=True, return an iterator.
    """
    run_dir = _run_dir(episode_id)
    if stream:
        def _it():
            for e in read_events(run_dir):
                yield e
        return _it()
    return read_events(run_dir)

def metrics(episode_id: str) -> Dict[str, Any]:
    """Convenience accessor: summary()['metrics']."""
    return summary(episode_id).get("metrics", {})

def list(limit: int = 50, since: str | None = None) -> List[Dict[str, Any]]:
    """
    List recent episodes with minimal fields.
    Not sorted strictly yet; will sort by started_at desc later.
    """
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
    """Return most recent episode_id if any."""
    rows = list(limit=1)
    return rows[0]["episode_id"] if rows else None

def paths(episode_id: str) -> Dict[str, str]:
    """Return canonical paths for dir, events, summary."""
    d = _run_dir(episode_id)
    return {
        "dir": str(d),
        "events": str(d / EVENTS_FILE),
        "summary": str(d / SUMMARY_FILE),
    }

# Helpers 

def _run_dir(episode_id: str) -> Path:
    return Path(_cfg.get()["runs_dir"]) / episode_id