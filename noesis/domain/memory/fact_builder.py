"""Builders for deriving long-term memory facts from episode artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

from ...interfaces.memory import Fact

__all__ = ["build_episode_fact"]


def build_episode_fact(summary: Mapping[str, Any], *, run_dir: Path) -> Fact:
    """Create a persistent memory fact representing an episode summary."""
    episode_id = str(summary.get("episode_id") or "").strip()
    if not episode_id:
        raise ValueError("summary missing 'episode_id'")

    task = str(summary.get("task") or "").strip()
    content = task or f"Episode {episode_id}"

    metrics = summary.get("metrics") or {}
    tags = summary.get("tags") or {}
    flags = summary.get("flags") or {}
    ports = summary.get("ports") or {}

    metadata: Dict[str, Any] = {
        "episode_id": episode_id,
        "task": task,
        "started_at": summary.get("started_at"),
        "duration_sec": summary.get("duration_sec"),
        "flags": dict(flags),
        "tags": dict(tags),
        "metrics": dict(metrics),
        "ports": dict(ports),
        "artifacts": {
            "summary": str(run_dir / "summary.json"),
            "events": str(run_dir / "events.jsonl"),
            "state": str(run_dir / "state.json"),
            "learn": str(run_dir / "learn.jsonl"),
        },
    }

    return Fact(
        id=f"episode:{episode_id}",
        content=content,
        metadata=metadata,
    )
