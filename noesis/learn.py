"""
Helper utilities for Noēsis.

Encodes the learn-mode lifecycle (off|record|apply), proposal
representation, scoring hooks, and persistence helpers for snapshots
and per-episode logs. Core orchestrates when to call into these helpers.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json

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


class LearnMode(str, Enum):
    OFF = "off"
    RECORD = "record"
    APPLY = "apply"


class LearnStatus(str, Enum):
    RECORDED = "recorded"
    SCORED = "scored"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"


@dataclass(slots=True)
class LearnProposal:
    """
    Structured learn proposal emitted per episode.
    """

    proposal_id: str
    policy_id: Optional[str]
    policy_version: Optional[str]
    kind: str
    target: Dict[str, Any]
    rationale: Optional[str] = None
    evidence_ids: List[str] = field(default_factory=list)
    score_fn: str = "heuristic"
    score: Optional[float] = None
    confidence: float = 0.0
    status: str = LearnStatus.RECORDED.value
    metadata: Dict[str, Any] = field(default_factory=dict)
    revert_handle: Optional[Dict[str, Any]] = None
    accepted: bool = False

    def mark_scored(self, *, score: float, confidence: float, scorer: str) -> None:
        self.score = float(score)
        self.confidence = max(0.0, min(1.0, float(confidence)))
        self.metadata.setdefault("scorer", scorer)
        if self.status == LearnStatus.RECORDED.value:
            self.status = LearnStatus.SCORED.value

    def approve(self) -> None:
        if self.status not in (LearnStatus.APPLIED.value, LearnStatus.REJECTED.value):
            self.status = LearnStatus.APPROVED.value

    def mark_applied(self, revert_handle: Dict[str, Any]) -> None:
        self.status = LearnStatus.APPLIED.value
        self.accepted = True
        self.revert_handle = revert_handle

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "proposal_id": self.proposal_id,
            "policy_version": self.policy_version,
            "kind": self.kind,
            "target": self.target,
            "rationale": self.rationale,
            "evidence_ids": self.evidence_ids,
            "score_fn": self.score_fn,
            "score": self.score,
            "confidence": self.confidence,
            "status": self.status,
            "metadata": self.metadata or {},
            "accepted": self.accepted,
        }
        if self.revert_handle:
            payload["revert_handle"] = self.revert_handle
        return payload


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_policy_id(policy_id: str) -> str:
    return policy_id.replace("/", "_").replace(" ", "_")


def derive_target_key(target: Dict[str, Any], *, fallback: str) -> str:
    path = target.get("path")
    if path:
        return str(path)
    return fallback


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
    """Write per-episode learn proposals under the episode directory."""
    path = run_dir / "learn.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"timestamp": _now(), "payload": payload}, ensure_ascii=False) + "\n")


def load_policy_snapshot(learn_home: Path, policy_id: str) -> Dict[str, Any]:
    """Load existing policy snapshot if present; returns a default skeleton otherwise."""
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
    """Persist cumulative learn state per policy."""
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
            gate_entry = gates.setdefault(key, {})
            gate_entry.update(info)

    with snapshot_path.open("w", encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=2)


def summarise_learn_kinds(proposals: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = Counter(p.get("kind", "unknown") for p in proposals)
    return dict(counts)
