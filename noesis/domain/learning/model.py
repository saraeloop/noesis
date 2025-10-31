"""Domain models for the Noēsis learning loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

__all__ = [
    "LearnMode",
    "LearnStatus",
    "LearnProposal",
    "derive_target_key",
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


def derive_target_key(target: Dict[str, Any], *, fallback: str) -> str:
    path = target.get("path")
    if path:
        return str(path)
    return fallback
