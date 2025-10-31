"""Learning utilities wrapping domain models with persistence helpers."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from noesis.domain.learning.model import (
    LearnMode,
    LearnProposal,
    LearnStatus,
    derive_target_key,
)

__all__ = [
    "LearnMode",
    "LearnStatus",
    "LearnProposal",
    "build_learn_payload",
    "persist_episode_learning",
    "load_policy_snapshot",
    "update_policy_snapshot",
    "derive_target_key",
    "summarise_learn_kinds",
]


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
    proposals: List[LearnProposal],
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
        "proposal": [p.to_dict() for p in proposals],
        "applied": applied,
        "scope": scope,
        "ttl": ttl,
        "approval": approval,
    }


def persist_episode_learning(run_dir: Path, payload: Dict[str, Any]) -> None:
    path = run_dir / "learn.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": _now(), "payload": payload}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_policy_snapshot(learn_home: Path, policy_id: str) -> Dict[str, Any]:
    policies_dir = learn_home / "policies"
    snapshot_path = policies_dir / f"{_sanitize_policy_id(policy_id)}.json"
    if snapshot_path.exists():
        with snapshot_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    return {
        "policy_id": policy_id,
        "tuning": {},
        "stats": {"episodes": 0},
        "history": [],
        "gates": {},
    }


def update_policy_snapshot(
    learn_home: Path,
    policy_id: str,
    proposals: List[Dict[str, Any]],
    *,
    gate_updates: Optional[Dict[str, Dict[str, Any]]] = None,
) -> None:
    if not policy_id:
        return
    policies_dir = learn_home / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = policies_dir / f"{_sanitize_policy_id(policy_id)}.json"

    snapshot = load_policy_snapshot(learn_home, policy_id)
    snapshot["updated_at"] = _now()
    stats = snapshot.setdefault("stats", {})
    stats["episodes"] = int(stats.get("episodes", 0)) + 1

    history = snapshot.setdefault("history", [])
    tuning = snapshot.setdefault("tuning", {})
    gates = snapshot.setdefault("gates", {})

    for item in proposals:
        target = item.get("target", {})
        path = target.get("path")
        status = item.get("status")
        history.append(
            {
                "ts": _now(),
                "proposal_id": item.get("proposal_id"),
                "kind": item.get("kind"),
                "target": target,
                "score": item.get("score"),
                "confidence": item.get("confidence"),
                "status": status,
                "revert_handle": item.get("revert_handle"),
            }
        )
        if status == LearnStatus.APPLIED.value and item.get("accepted") and path:
            tuning[path] = target.get("to")

    if gate_updates:
        for key, info in gate_updates.items():
            gates.setdefault(key, {}).update(info)

    with snapshot_path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2)


def summarise_learn_kinds(proposals: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter(p.get("kind", "unknown") for p in proposals)
    return dict(counts)
