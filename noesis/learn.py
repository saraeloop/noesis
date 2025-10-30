"""
Learning helper utilities for Noēsis.

Encodes the learn-mode lifecycle (off|record|apply), proposal
representation, and persistence helpers for snapshots and per-episode
logs. Core orchestrates when to call into these helpers.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json

__all__ = [
    "LearnMode",
    "build_learn_payload",
    "persist_episode_learning",
    "update_policy_snapshot",
    "summarise_learn_kinds",
]


class LearnMode(str, Enum):
    OFF = "off"
    RECORD = "record"
    APPLY = "apply"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_policy_id(policy_id: str) -> str:
    return policy_id.replace("/", "_").replace(" ", "_")


def build_learn_payload(
    *,
    policy_id: str | None,
    metrics: Dict[str, Any],
    reasons: Iterable[str],
    latencies: Dict[str, Any],
    counts: Dict[str, int],
    proposals: List[Dict[str, Any]],
    applied: bool,
    scope: str = "policy",
    ttl: Any = None,
    proposal_id: Optional[str] = None,
    approval: str = "pending",
) -> Dict[str, Any]:
    return {
        "id": proposal_id,
        "policy_id": policy_id,
        "basis": {
            "success": metrics.get("success"),
            "reasons": list(reasons),
            "latencies": latencies,
            "counts": counts,
        },
        "proposal": proposals,
        "applied": applied,
        "scope": scope,
        "ttl": ttl,
        "approval": approval,
    }


def persist_episode_learning(run_dir: Path, payload: Dict[str, Any]) -> None:
    """Write per-episode learn proposals under the episode directory."""
    path = run_dir / "learn.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": _now(), "payload": payload}, ensure_ascii=False) + "\n")


def update_policy_snapshot(
    learn_home: Path,
    policy_id: str,
    proposals: List[Dict[str, Any]],
    *,
    applied: bool,
) -> None:
    """Persist cumulative learn state per policy."""
    if not policy_id:
        return
    policies_dir = learn_home / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = policies_dir / f"{_sanitize_policy_id(policy_id)}.json"

    if snapshot_path.exists():
        with snapshot_path.open("r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
    else:
        snapshot = {
            "policy_id": policy_id,
            "tuning": {},
            "stats": {"episodes": 0},
            "history": [],
        }

    snapshot["updated_at"] = _now()
    stats = snapshot.setdefault("stats", {})
    stats["episodes"] = int(stats.get("episodes", 0)) + 1

    history = snapshot.setdefault("history", [])

    if applied:
        for item in proposals:
            if item.get("accepted"):
                path = item.get("path")
                snapshot.setdefault("tuning", {})
                if path:
                    snapshot["tuning"][path] = item.get("to")
                history.append(
                    {
                        "ts": _now(),
                        "kind": item.get("kind"),
                        "path": path,
                        "from": item.get("from"),
                        "to": item.get("to"),
                        "why": item.get("reason"),
                    }
                )

    with snapshot_path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2)


def summarise_learn_kinds(proposals: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter(p.get("kind", "unknown") for p in proposals)
    return dict(counts)
