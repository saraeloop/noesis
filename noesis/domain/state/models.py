"""
Domain data models for the Noēsis cognitive state.

These dataclasses are framework-agnostic and avoid any direct I/O so they
can be reused across application services and adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, TYPE_CHECKING
import itertools

if TYPE_CHECKING:
    from noesis.domain.faculties.intuition import IntuitionMode

STATE_VERSION = "1.0"
STATE_SCHEMA_VERSION = "1.0.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _default_intuition_mode() -> "IntuitionMode":
    from noesis.domain.faculties.intuition import IntuitionMode

    return IntuitionMode.ADVISORY


class PlanKind(str, Enum):
    DETECT = "detect"
    ANALYZE = "analyze"
    PLAN = "plan"
    ACT = "act"
    VERIFY = "verify"
    REVIEW = "review"
    DEFAULT = "plan"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"
    VETOED = "vetoed"


class OutcomeStatus(str, Enum):
    PENDING = "pending"
    OK = "ok"
    ERROR = "error"
    VETOED = "vetoed"
    ABORTED = "aborted"
    PARTIAL = "partial"


PLAN_KINDS_DEFAULT = PlanKind.DEFAULT.value
OUTCOME_STATUS_OK = OutcomeStatus.OK.value
OUTCOME_STATUS_ERROR = OutcomeStatus.ERROR.value
OUTCOME_STATUS_VETOED = OutcomeStatus.VETOED.value
OUTCOME_STATUS_ABORTED = OutcomeStatus.ABORTED.value
OUTCOME_STATUS_PARTIAL = OutcomeStatus.PARTIAL.value


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
        payload.update({k: v for k, v in self.extensions.items() if k.startswith("x-")})
        return payload


@dataclass(slots=True)
class PlanStep:
    id: str
    kind: PlanKind
    description: str
    status: StepStatus = StepStatus.PENDING
    rationale: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "id": self.id,
            "kind": self.kind.value,
            "description": self.description,
            "status": self.status.value,
        }
        if self.rationale:
            payload["rationale"] = self.rationale
        if self.depends_on:
            payload["depends_on"] = list(dict.fromkeys(self.depends_on))
        if self.inputs:
            payload["inputs"] = self.inputs
        if self.outputs:
            payload["outputs"] = self.outputs
        payload.update({k: v for k, v in self.extensions.items() if k.startswith("x-")})
        return payload


@dataclass(slots=True)
class MemoryFact:
    type: str
    key: str
    value: Any
    timestamp: str = field(default_factory=_now_iso)
    ttl_sec: Optional[int] = None
    provenance: Optional[Provenance] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "type": self.type,
            "key": self.key,
            "value": self.value,
            "timestamp": self.timestamp,
        }
        if self.ttl_sec is not None:
            payload["ttl_sec"] = int(self.ttl_sec)
        if self.provenance:
            payload["provenance"] = self.provenance.to_dict()
        payload.update({k: v for k, v in self.extensions.items() if k.startswith("x-")})
        return payload


@dataclass(slots=True)
class ActionArtifact:
    type: str
    uri: str
    sha256: Optional[str] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {"type": self.type, "uri": self.uri}
        if self.sha256:
            payload["sha256"] = self.sha256
        payload.update({k: v for k, v in self.extensions.items() if k.startswith("x-")})
        return payload


@dataclass(slots=True)
class ActionRecord:
    id: str
    kind: str
    tool: str
    input_excerpt: str
    result_status: str
    timestamp: str = field(default_factory=_now_iso)
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
        payload.update({k: v for k, v in self.extensions.items() if k.startswith("x-")})
        return payload


@dataclass(slots=True)
class NoesisState:
    episode_id: str
    seed: int
    task: str
    started_at: str
    tags: Dict[str, Any]
    adapter_label: str
    process_id: str | None = None
    process_name: str | None = None
    process_kind: str | None = None
    process_run_index: int | None = None
    intuition_mode: "IntuitionMode" = field(default_factory=_default_intuition_mode)
    plan_steps: List[PlanStep] = field(default_factory=list)
    plan_rationale: Optional[str] = None
    plan_source: str = "planner"
    plan_updated_at: str = field(default_factory=_now_iso)
    beliefs: List[Dict[str, Any]] = field(default_factory=list)
    memory_facts: List[MemoryFact] = field(default_factory=list)
    scratchpad: str = ""
    outcome_status: OutcomeStatus = OutcomeStatus.PENDING
    outcome_summary: Optional[str] = None
    outcome_metrics: Dict[str, Any] = field(default_factory=dict)
    actions: List[ActionRecord] = field(default_factory=list)
    links: Dict[str, str] = field(default_factory=dict)
    _action_counter: itertools.count = field(default_factory=lambda: itertools.count(1), init=False, repr=False)

    def set_plan(
        self,
        steps: Iterable[PlanStep],
        rationale: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        self.plan_steps = [step for step in steps]
        self.plan_rationale = rationale
        if source:
            self.plan_source = source
        self.plan_updated_at = _now_iso()

    def add_belief(self, *, statement: str, confidence: float, provenance: Provenance) -> None:
        self.beliefs.append(
            {
                "statement": statement,
                "confidence": max(0.0, min(1.0, float(confidence))),
                "timestamp": _now_iso(),
                "provenance": provenance.to_dict(),
            }
        )

    def set_scratchpad(self, text: str) -> None:
        self.scratchpad = text

    def add_memory_fact(self, fact: MemoryFact) -> None:
        self.memory_facts.append(fact)

    def record_action(
        self,
        *,
        kind: str,
        tool: str,
        input_excerpt: str,
        result_status: str,
        step_id: Optional[str] = None,
        provenance: Optional[Provenance] = None,
        result_artifacts: Optional[Sequence[ActionArtifact | Dict[str, Any]]] = None,
        extensions: Optional[Dict[str, Any]] = None,
    ) -> ActionRecord:
        action_id = f"act-{next(self._action_counter)}"
        artifacts: List[ActionArtifact] = []
        for item in result_artifacts or ():
            if isinstance(item, ActionArtifact):
                artifacts.append(item)
            else:
                artifacts.append(ActionArtifact(**item))
        prov_obj = provenance
        if provenance and not isinstance(provenance, Provenance):
            prov_obj = Provenance(**provenance)
        action = ActionRecord(
            id=action_id,
            kind=kind,
            tool=tool,
            input_excerpt=input_excerpt,
            result_status=result_status,
            step_id=step_id,
            provenance=prov_obj,
            result_artifacts=artifacts,
            extensions=extensions or {},
        )
        self.actions.append(action)
        return action

    def set_outcome(
        self,
        *,
        status: OutcomeStatus | str,
        summary: Optional[str],
        metrics: Optional[Dict[str, Any]],
    ) -> None:
        self.outcome_status = status if isinstance(status, OutcomeStatus) else OutcomeStatus(status)
        self.outcome_summary = summary
        if metrics:
            self.outcome_metrics = dict(metrics)

    def set_links(self, **links: str) -> None:
        self.links = {k: v for k, v in links.items() if v}

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "version": STATE_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
            "episode": {
                "id": self.episode_id,
                "seed": self.seed,
                "started_at": self.started_at,
                "tags": self.tags,
                "using": self.adapter_label,
                "intuition_mode": self.intuition_mode.value,
            },
            "goal": {"task": self.task, "type": "task"},
            "beliefs": list(self.beliefs),
            "plan": {
                "steps": [step.to_dict() for step in self.plan_steps],
                "source": self.plan_source,
                "updated_at": self.plan_updated_at,
                **({"rationale": self.plan_rationale} if self.plan_rationale else {}),
            },
            "memory": {
                "facts": [fact.to_dict() for fact in self.memory_facts],
                "scratchpad": self.scratchpad,
            },
            "outcomes": {
                "status": self.outcome_status.value,
                "summary": self.outcome_summary,
                "actions": [action.to_dict() for action in self.actions],
                "metrics": self.outcome_metrics,
            },
            "links": self.links,
        }
        if self.process_id and self.process_name:
            payload["process"] = {
                "id": self.process_id,
                "name": self.process_name,
                "run_index": self.process_run_index,
                "kind": self.process_kind,
            }
        return payload

    @property
    def plan(self) -> "_PlanView":
        return _PlanView(self)

    @property
    def outcomes(self) -> "_OutcomesView":
        return _OutcomesView(self)


class _PlanView:
    def __init__(self, state: NoesisState) -> None:
        self._state = state

    @property
    def steps(self) -> List[PlanStep]:
        return self._state.plan_steps


class _OutcomesView:
    def __init__(self, state: NoesisState) -> None:
        self._state = state

    @property
    def status(self) -> str:
        return self._state.outcome_status.value

    @property
    def summary(self) -> Optional[str]:
        return self._state.outcome_summary

    @property
    def actions(self) -> List[ActionRecord]:
        return self._state.actions

    @property
    def metrics(self) -> Dict[str, Any]:
        return self._state.outcome_metrics


def create_state(
    *,
    episode_id: str,
    seed: int,
    task: str,
    started_at: str,
    tags: Dict[str, Any],
    adapter_label: str,
    process_id: str | None = None,
    process_name: str | None = None,
    process_kind: str | None = None,
    process_run_index: int | None = None,
    intuition_mode: "IntuitionMode | None" = None,
) -> NoesisState:
    """Factory to instantiate a state with immutable metadata."""
    if intuition_mode is None:
        intuition_mode = _default_intuition_mode()
    return NoesisState(
        episode_id=episode_id,
        seed=seed,
        task=task,
        started_at=started_at,
        tags=tags,
        adapter_label=adapter_label,
        process_id=process_id,
        process_name=process_name,
        process_kind=process_kind,
        process_run_index=process_run_index,
        intuition_mode=intuition_mode,
    )
