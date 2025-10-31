"""
Noēsis State v1 data model.

Defines the canonical cognitive state payload recorded alongside every
episode. Policies and adapters can rely on this structure when inspecting
or mutating an agent’s plan, beliefs, or memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import itertools
import json

STATE_VERSION = "1.0"
STATE_SCHEMA_VERSION = "1.0.0"

PLAN_KINDS_DEFAULT = "plan"
PLAN_STATUS_PENDING = "pending"
PLAN_STATUS_DONE = "done"
OUTCOME_STATUS_PENDING = "pending"
OUTCOME_STATUS_OK = "ok"
OUTCOME_STATUS_ERROR = "error"
OUTCOME_STATUS_VETOED = "vetoed"
OUTCOME_STATUS_ABORTED = "aborted"
OUTCOME_STATUS_PARTIAL = "partial"

__all__ = [
    "STATE_VERSION",
    "STATE_SCHEMA_VERSION",
    "PlanStep",
    "NoesisState",
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _filter_extensions(data: Dict[str, Any]) -> Dict[str, Any]:
    """Keep `x-` extension keys while dropping empty mappings."""
    return {k: v for k, v in data.items() if k.startswith("x-")}


@dataclass(slots=True)
class Provenance:
    source: str
    evidence_ids: List[str] = field(default_factory=list)
    policy_id: Optional[str] = None
    adapter_id: Optional[str] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"source": self.source}
        if self.evidence_ids:
            payload["evidence_ids"] = list(self.evidence_ids)
        if self.policy_id:
            payload["policy_id"] = self.policy_id
        if self.adapter_id:
            payload["adapter_id"] = self.adapter_id
        payload.update(_filter_extensions(self.extensions))
        return payload


@dataclass(slots=True)
class PlanStep:
    """
    Canonical plan step structure.
    """

    id: str
    kind: str
    description: str
    status: str = PLAN_STATUS_PENDING
    rationale: Optional[str] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "description": self.description,
            "status": self.status,
        }
        if self.rationale:
            payload["rationale"] = self.rationale
        if self.inputs:
            payload["inputs"] = self.inputs
        if self.outputs:
            payload["outputs"] = self.outputs
        if self.depends_on:
            payload["depends_on"] = list(dict.fromkeys(self.depends_on))
        payload.update(_filter_extensions(self.extensions))
        return payload


@dataclass(slots=True)
class MemoryFact:
    type: str
    key: str
    value: Any
    provenance: Optional[Provenance] = None
    timestamp: Optional[str] = None
    ttl_sec: Optional[int] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "type": self.type,
            "key": self.key,
            "value": self.value,
        }
        if self.provenance:
            payload["provenance"] = self.provenance.to_dict()
        if self.timestamp:
            payload["timestamp"] = self.timestamp
        if self.ttl_sec is not None:
            payload["ttl_sec"] = int(self.ttl_sec)
        payload.update(_filter_extensions(self.extensions))
        return payload


@dataclass(slots=True)
class ActionArtifact:
    type: str
    uri: str
    sha256: Optional[str] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"type": self.type, "uri": self.uri}
        if self.sha256:
            payload["sha256"] = self.sha256
        payload.update(_filter_extensions(self.extensions))
        return payload


@dataclass(slots=True)
class ActionRecord:
    id: str
    kind: str
    tool: str
    input_excerpt: str
    result_status: str
    timestamp: str
    step_id: Optional[str] = None
    provenance: Optional[Provenance] = None
    result_artifacts: List[ActionArtifact] = field(default_factory=list)
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "tool": self.tool,
            "input_excerpt": self.input_excerpt,
            "result_status": self.result_status,
            "timestamp": self.timestamp,
        }
        if self.step_id:
            payload["step_id"] = self.step_id
        if self.provenance:
            payload["provenance"] = self.provenance.to_dict()
        if self.result_artifacts:
            payload["result_artifacts"] = [artifact.to_dict() for artifact in self.result_artifacts]
        payload.update(_filter_extensions(self.extensions))
        return payload


@dataclass(slots=True)
class _Plan:
    steps: List[PlanStep] = field(default_factory=list)
    rationale: Optional[str] = None
    source: str = "system"
    updated_at: str = field(default_factory=_now_iso)
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "steps": [step.to_dict() for step in self.steps],
            "source": self.source,
            "updated_at": self.updated_at,
        }
        if self.rationale:
            payload["rationale"] = self.rationale
        payload.update(_filter_extensions(self.extensions))
        return payload


@dataclass(slots=True)
class _Memory:
    facts: List[MemoryFact] = field(default_factory=list)
    scratchpad: str = ""
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "facts": [fact.to_dict() for fact in self.facts],
        }
        if self.scratchpad:
            payload["scratchpad"] = self.scratchpad
        payload.update(_filter_extensions(self.extensions))
        return payload


@dataclass(slots=True)
class _Outcomes:
    status: str = OUTCOME_STATUS_PENDING
    summary: Optional[str] = None
    actions: List[ActionRecord] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[ActionArtifact] = field(default_factory=list)
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "status": self.status,
            "actions": [action.to_dict() for action in self.actions],
        }
        if self.summary:
            payload["summary"] = self.summary
        if self.metrics:
            payload["metrics"] = self.metrics
        if self.artifacts:
            payload["artifacts"] = [artifact.to_dict() for artifact in self.artifacts]
        payload.update(_filter_extensions(self.extensions))
        return payload


@dataclass(slots=True)
class _EpisodeInfo:
    episode_id: str
    seed: int
    started_at: str
    tags: Dict[str, Any] = field(default_factory=dict)
    using: Optional[str] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.episode_id,
            "seed": self.seed,
            "started_at": self.started_at,
            "tags": self.tags,
        }
        if self.using:
            payload["using"] = self.using
        payload.update(_filter_extensions(self.extensions))
        return payload


@dataclass(slots=True)
class _Goal:
    task: str
    context: Optional[str] = None
    type: str = "task"
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"task": self.task, "type": self.type}
        if self.context:
            payload["context"] = self.context
        payload.update(_filter_extensions(self.extensions))
        return payload


class NoesisState:
    """
    Lightweight container for the Noēsis cognitive state.
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
        self.links: Dict[str, str] = {}
        self._action_counter = itertools.count(1)

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

    def add_belief(
        self,
        *,
        statement: str,
        confidence: float,
        provenance: Provenance | Dict[str, Any],
    ) -> None:
        prov_obj = provenance if isinstance(provenance, Provenance) else Provenance(**provenance)
        self.beliefs.append(
            {
                "statement": statement,
                "confidence": max(0.0, min(1.0, float(confidence))),
                "timestamp": _now_iso(),
                "provenance": prov_obj.to_dict(),
            }
        )

    def set_scratchpad(self, text: str) -> None:
        self.memory.scratchpad = text

    def add_memory_fact(
        self,
        *,
        type: str,
        key: str,
        value: Any,
        provenance: Optional[Provenance | Dict[str, Any]] = None,
        ttl_sec: Optional[int] = None,
        timestamp: Optional[str] = None,
    ) -> None:
        prov_obj = None
        if provenance:
            prov_obj = provenance if isinstance(provenance, Provenance) else Provenance(**provenance)
        fact = MemoryFact(
            type=type,
            key=key,
            value=value,
            provenance=prov_obj,
            ttl_sec=ttl_sec,
            timestamp=timestamp or _now_iso(),
        )
        self.memory.facts.append(fact)

    def record_action(
        self,
        *,
        kind: str,
        tool: str,
        input_excerpt: str,
        result_status: str,
        step_id: Optional[str] = None,
        provenance: Optional[Provenance | Dict[str, Any]] = None,
        result_artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> ActionRecord:
        action_id = f"act-{next(self._action_counter)}"
        prov_obj = None
        if provenance:
            prov_obj = provenance if isinstance(provenance, Provenance) else Provenance(**provenance)
        artifacts = [
            ActionArtifact(**artifact) if not isinstance(artifact, ActionArtifact) else artifact
            for artifact in (result_artifacts or [])
        ]
        action = ActionRecord(
            id=action_id,
            kind=kind,
            tool=tool,
            input_excerpt=input_excerpt,
            result_status=result_status,
            timestamp=_now_iso(),
            step_id=step_id,
            provenance=prov_obj,
            result_artifacts=artifacts,
        )
        self.outcomes.actions.append(action)
        return action

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

    def set_links(self, *, events: Optional[str] = None, summary: Optional[str] = None, learn: Optional[str] = None) -> None:
        links: Dict[str, str] = {}
        if events:
            links["events"] = events
        if summary:
            links["summary"] = summary
        if learn:
            links["learn"] = learn
        self.links = links

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "version": self.version,
            "state_schema_version": self.state_schema_version,
            "episode": self.episode.to_dict(),
            "goal": self.goal.to_dict(),
            "beliefs": list(self.beliefs),
            "plan": self.plan.to_dict(),
            "memory": self.memory.to_dict(),
            "outcomes": self.outcomes.to_dict(),
        }
        if self.links:
            payload["links"] = self.links
        return payload

    def write(self, path: Path) -> None:
        payload = self.to_dict()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
