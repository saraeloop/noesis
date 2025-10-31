"""
Noēsis State v1 data model.

Defines the canonical cognitive state payload recorded alongside every
episode. Policies and adapters can rely on this structure when inspecting
or mutating an agent’s plan, beliefs, or memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json

STATE_VERSION = "1.0"
STATE_SCHEMA_VERSION = "1.0.0"

__all__ = [
    "STATE_VERSION",
    "PlanStep",
    "STATE_SCHEMA_VERSION",
    "NoesisState",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class PlanStep:
    """
    Canonical plan step structure.

    `kind` can be used by planners to differentiate detector/action/verify
    patterns. `status` reflects runtime progress.
    """

    id: str
    kind: str
    description: str
    status: str = "pending"
    rationale: Optional[str] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if not data.get("depends_on"):
            data.pop("depends_on", None)
        if not data.get("inputs"):
            data.pop("inputs", None)
        if not data.get("outputs"):
            data.pop("outputs", None)
        if self.rationale is None:
            data.pop("rationale", None)
        return data


@dataclass(slots=True)
class _Plan:
    steps: List[PlanStep] = field(default_factory=list)
    rationale: Optional[str] = None
    source: str = "system"
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "steps": [step.to_dict() for step in self.steps],
            "source": self.source,
            "updated_at": self.updated_at,
        }
        if self.rationale:
            data["rationale"] = self.rationale
        return data


@dataclass(slots=True)
class _Memory:
    facts: List[Dict[str, Any]] = field(default_factory=list)
    scratchpad: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = {"facts": self.facts}
        if self.scratchpad:
            data["scratchpad"] = self.scratchpad
        return data


@dataclass(slots=True)
class _Outcomes:
    status: str = "pending"
    summary: Optional[str] = None
    actions: List[Dict[str, Any]] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "status": self.status,
            "actions": self.actions,
        }
        if self.summary:
            data["summary"] = self.summary
        if self.metrics:
            data["metrics"] = self.metrics
        if self.artifacts:
            data["artifacts"] = self.artifacts
        return data


@dataclass(slots=True)
class _EpisodeInfo:
    episode_id: str
    seed: int
    started_at: str
    tags: Dict[str, Any] = field(default_factory=dict)
    using: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": self.episode_id,
            "seed": self.seed,
            "started_at": self.started_at,
            "tags": self.tags,
        }
        if self.using:
            data["using"] = self.using
        return data


@dataclass(slots=True)
class _Goal:
    task: str
    context: Optional[str] = None
    type: str = "task"

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {"task": self.task, "type": self.type}
        if self.context:
            data["context"] = self.context
        return data


class NoesisState:
    """
    Lightweight container for the Noēsis cognitive state.

    The structure mirrors the public schema ({episode, goal, beliefs, plan,
    memory, outcomes}). Methods mutate the in-memory representation and persist
    it to disk.
    """

    def __init__(
        self,
        *,
        episode: _EpisodeInfo,
        goal: _Goal,
        beliefs: Optional[List[Dict[str, Any]]] = None,
        plan: Optional[_Plan] = None,
        memory: Optional[_Memory] = None,
        outcomes: Optional[_Outcomes] = None,
    ) -> None:
        self.version = STATE_VERSION
        self.state_schema_version = STATE_SCHEMA_VERSION
        self.episode = episode
        self.goal = goal
        self.beliefs: List[Dict[str, Any]] = beliefs or []
        self.plan = plan or _Plan()
        self.memory = memory or _Memory()
        self.outcomes = outcomes or _Outcomes()

    @classmethod
    def new(
        cls,
        *,
        episode_id: str,
        seed: int,
        task: str,
        started_at: str,
        tags: Optional[Dict[str, Any]] = None,
        using: Optional[str] = None,
        context: Optional[str] = None,
    ) -> "NoesisState":
        episode = _EpisodeInfo(
            episode_id=episode_id,
            seed=seed,
            started_at=started_at,
            tags=dict(tags or {}),
            using=using,
        )
        goal = _Goal(task=task, context=context)
        return cls(episode=episode, goal=goal)

    def set_plan(
        self,
        *,
        steps: Iterable[PlanStep],
        rationale: Optional[str],
        source: str,
    ) -> None:
        self.plan = _Plan(steps=list(steps), rationale=rationale, source=source, updated_at=_now_iso())

    def record_action(self, action: Dict[str, Any]) -> None:
        action = dict(action)
        if "timestamp" not in action:
            action["timestamp"] = _now_iso()
        self.outcomes.actions.append(action)

    def set_outcome(
        self,
        *,
        status: str,
        summary: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.outcomes.status = status
        self.outcomes.summary = summary
        if metrics:
            self.outcomes.metrics = dict(metrics)

    def add_belief(self, *, statement: str, confidence: float, source: str) -> None:
        self.beliefs.append(
            {
                "statement": statement,
                "confidence": max(0.0, min(1.0, float(confidence))),
                "source": source,
                "timestamp": _now_iso(),
            }
        )

    def set_scratchpad(self, text: str) -> None:
        self.memory.scratchpad = text

    def add_memory_fact(self, fact: Dict[str, Any]) -> None:
        payload = dict(fact)
        payload.setdefault("timestamp", _now_iso())
        self.memory.facts.append(payload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "state_schema_version": self.state_schema_version,
            "episode": self.episode.to_dict(),
            "goal": self.goal.to_dict(),
            "beliefs": list(self.beliefs),
            "plan": self.plan.to_dict(),
            "memory": self.memory.to_dict(),
            "outcomes": self.outcomes.to_dict(),
        }

    def write(self, path: Path) -> None:
        payload = self.to_dict()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
