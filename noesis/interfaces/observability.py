"""
Runtime observability adapters.

Bridges the domain event bus contract with the existing runtime event
emission helpers so the use cases remain framework-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Mapping, Sequence
from uuid import UUID, uuid4

from noesis.domain.planner.interfaces import EventBus
from noesis.domain.faculties.direction import PlannerDirective
from noesis.domain.faculties.governance import GovernanceResult
from noesis.domain.action_candidates import ActionCandidate
from noesis.domain.state import (
    ActionRecord,
    CognitiveEvent,
    CognitiveMetrics,
    CognitiveVerb,
    LineageTracker,
    PlanStep,
)
from noesis.infrastructure.state_repository import EpisodeContext
from noesis.runtime.clock import RuntimeClock
from noesis.runtime.events_emitter import CognitiveEventEmitter
from noesis.runtime.events import (
    action_candidate_event as _action_candidate_event,
    direction_event as _direction_event,
    governance_event as _governance_event,
)


@dataclass(slots=True)
class RuntimeEventBus(EventBus):
    """Concrete event bus that writes to the runtime JSONL logs."""

    context: EpisodeContext
    emitter: CognitiveEventEmitter
    lineage: LineageTracker
    clock: RuntimeClock = field(default_factory=RuntimeClock)
    now: Callable[[], datetime] = field(default_factory=lambda: (lambda: datetime.now(timezone.utc)))
    event_id_factory: Callable[[], UUID] = uuid4
    _plan_steps: list[str] = field(default_factory=list, init=False, repr=False)
    _reflect_snapshot: dict[str, object] = field(default_factory=dict, init=False, repr=False)

    def emit_plan(
        self,
        *,
        steps: Sequence[PlanStep],
        rationale: str,
        source: str,
        metrics: CognitiveMetrics | None = None,
        caused_by: UUID | None = None,
    ) -> CognitiveEvent:
        self._plan_steps = [step.id for step in steps]
        if metrics is not None and caused_by is not None:
            self.lineage.seed(last_event_id=caused_by)
        labels = [f"{step.kind.value}:{step.description}" for step in steps]
        payload = {"steps": labels}
        if rationale:
            payload["rationale"] = rationale
        event_metrics = metrics or self._instant_metric(CognitiveVerb.PLAN)
        event = CognitiveEvent(
            episode_id=self.context.episode_id,
            verb=CognitiveVerb.PLAN,
            payload=payload,
            timestamp=event_metrics.completed_at,
            event_id=self.event_id_factory(),
        )
        if event_metrics:
            event = event.with_metrics(event_metrics)
        linked = self.lineage.register(event, cause=self.lineage.last_event_id if caused_by is None else caused_by)  # type: ignore[arg-type]
        self.emitter.emit(linked, agent_id=source or "system")
        return linked

    def emit_direction(
        self,
        *,
        directive: PlannerDirective,
        caused_by: UUID | None = None,
    ) -> UUID:
        payload = directive.to_mapping()
        payload["policy"] = directive.policy_id
        return self.emit_direction_payload(
            payload=payload,
            agent_id=directive.policy_id,
            caused_by=caused_by,
        )

    def emit_direction_payload(
        self,
        *,
        payload: Mapping[str, object],
        agent_id: str,
        caused_by: UUID | None = None,
    ) -> UUID:
        return _direction_event(
            self.context.run_dir,
            self.context.episode_id,
            dict(payload),
            agent=agent_id,
            caused_by=str(caused_by) if caused_by else None,
            now_fn=lambda: self.now().isoformat(),
            id_factory=self.event_id_factory,
        )

    def emit_action_candidate(
        self,
        *,
        candidate: ActionCandidate,
        caused_by: UUID | None = None,
    ) -> UUID:
        payload = candidate.to_mapping()
        return _action_candidate_event(
            self.context.run_dir,
            self.context.episode_id,
            payload,
            agent=self.context.adapter_label,
            caused_by=str(caused_by) if caused_by else None,
            now_fn=lambda: self.now().isoformat(),
            id_factory=self.event_id_factory,
        )

    def emit_governance(
        self,
        *,
        result: GovernanceResult,
        caused_by: UUID | None = None,
    ) -> UUID:
        payload = result.to_mapping()
        event_id = _governance_event(
            self.context.run_dir,
            self.context.episode_id,
            payload,
            agent=result.policy_id,
            caused_by=str(caused_by) if caused_by else None,
            now_fn=lambda: self.now().isoformat(),
            id_factory=self.event_id_factory,
        )
        return event_id

    def emit_action(
        self,
        action: ActionRecord,
        *,
        metrics: CognitiveMetrics | None = None,
        caused_by: UUID | None = None,
    ) -> None:
        candidate_id = action.extensions.get("x-action_candidate_id") if action.extensions else None
        if candidate_id and caused_by is None:
            raise ValueError("action_candidate_id requires explicit caused_by for act lineage")
        payload = {
            "input_excerpt": action.input_excerpt,
            "outcome": action.result_status,
        }
        if candidate_id:
            payload["action_candidate_id"] = candidate_id
        if action.tool:
            payload["tool"] = action.tool
        metrics = metrics or self._instant_metric(CognitiveVerb.ACT)
        event = CognitiveEvent(
            episode_id=self.context.episode_id,
            verb=CognitiveVerb.ACT,
            payload=payload,
            timestamp=metrics.completed_at,
            event_id=self.event_id_factory(),
        )
        if metrics:
            event = event.with_metrics(metrics)
        linked = self.lineage.register(event, cause=self.lineage.last_event_id if caused_by is None else caused_by)  # type: ignore[arg-type]
        self.emitter.emit(linked, agent_id=action.tool or "system")

    def emit_reflect(
        self,
        *,
        success: bool,
        reasons: list[str],
        metrics: CognitiveMetrics | None = None,
        caused_by: UUID | None = None,
    ) -> None:
        self._reflect_snapshot = {"success": success, "reasons": list(reasons)}
        if metrics is not None:
            if caused_by is not None:
                self.lineage.seed(last_event_id=caused_by)
            return
        payload = {"success": success}
        if reasons:
            payload["reasons"] = reasons
        metrics = metrics or self._instant_metric(CognitiveVerb.REFLECT)
        event = CognitiveEvent(
            episode_id=self.context.episode_id,
            verb=CognitiveVerb.REFLECT,
            payload=payload,
            timestamp=metrics.completed_at,
            event_id=self.event_id_factory(),
        )
        if metrics:
            event = event.with_metrics(metrics)
        linked = self.lineage.register(event, cause=self.lineage.last_event_id if caused_by is None else caused_by)  # type: ignore[arg-type]
        self.emitter.emit(linked)

    def _instant_metric(self, verb: CognitiveVerb) -> CognitiveMetrics:
        token = self.clock.start(verb)
        return self.clock.stop(token)
