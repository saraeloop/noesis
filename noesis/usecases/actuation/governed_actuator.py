"""
Governed actuator wrapper for side-effectful execution.

This decorator enforces pre-act governance, emits action-candidate lineage,
and injects candidate metadata into act events without changing adapter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, Sequence
from uuid import UUID

from noesis.domain.action_candidates import ActionCandidate
from noesis.domain.actuation.models import ActuationResult as GovernedResult
from noesis.domain.actuation.models import ActuationStatus
from noesis.domain.faculties.governance import (
    GovernanceFailurePolicy,
    GovernanceMode,
    PreActGovernor,
)
from noesis.domain.planner.interfaces import ActuationResult, Actuator, EventBus, EpisodeRequest
from noesis.domain.state import ActionRecord, NoesisState, PlanStep
from noesis.usecases.action_gating import govern_pre_act_action


class ActionCandidateBuilder(Protocol):
    """Builds a deterministic action candidate from execution context."""

    def build(
        self,
        *,
        plan: Sequence[PlanStep],
        request: EpisodeRequest,
        state: NoesisState,
    ) -> ActionCandidate:
        ...


@dataclass(slots=True)
class GovernedActuator(Actuator):
    """Decorator that enforces governance before executing side effects."""

    inner: Actuator
    candidate_builder: ActionCandidateBuilder
    governance_policy: PreActGovernor | None
    governance_mode: GovernanceMode
    failure_policy: GovernanceFailurePolicy | None = None
    timeout_ms: int | None = None
    caused_by_resolver: (
        Callable[[Sequence[PlanStep], EpisodeRequest, NoesisState], UUID | None] | None
    ) = None

    def execute(
        self,
        *,
        plan: Sequence[PlanStep],
        request: EpisodeRequest,
        state: NoesisState,
        event_bus: EventBus,
    ) -> ActuationResult:
        candidate = self.candidate_builder.build(plan=plan, request=request, state=state)
        caused_by = (
            self.caused_by_resolver(plan, request, state)
            if self.caused_by_resolver is not None
            else None
        )
        gate = govern_pre_act_action(
            goal=request.goal,
            plan=plan,
            candidate=candidate,
            event_bus=event_bus,
            episode_id=request.episode_id,
            governance_policy=self.governance_policy,
            governance_mode=self.governance_mode,
            failure_policy=self.failure_policy,
            timeout_ms=self.timeout_ms,
            caused_by=caused_by,
        )
        if gate.terminal_outcome == "vetoed":
            return _as_legacy_result(
                GovernedResult(
                    status=ActuationStatus.BLOCKED,
                    summary=gate.governance_result.message
                    if gate.governance_result
                    else "Action vetoed by governance",
                    reasons=[gate.reason] if gate.reason else [],
                )
            )
        if gate.terminal_outcome == "error":
            return _as_legacy_result(
                GovernedResult(
                    status=ActuationStatus.ERROR,
                    summary=gate.governance_result.message
                    if gate.governance_result
                    else "Governance evaluation failed",
                    reasons=["governance_failure"],
                    error=gate.governance_result.error if gate.governance_result else None,
                )
            )

        if not gate.candidate.id:
            raise ValueError("ActionCandidate.id must be set before act emission")
        act_cause = gate.governance_event_id or gate.candidate_event_id
        guarded_bus = _ActionCandidateEventBus(
            base=event_bus,
            candidate_id=gate.candidate.id,
            caused_by=act_cause,
        )
        return self.inner.execute(
            plan=plan,
            request=request,
            state=state,
            event_bus=guarded_bus,
        )


@dataclass(slots=True)
class _ActionCandidateEventBus(EventBus):
    base: EventBus
    candidate_id: str
    caused_by: UUID | None

    def emit_plan(self, **kwargs):  # type: ignore[no-untyped-def]
        return self.base.emit_plan(**kwargs)

    def emit_direction(self, **kwargs):  # type: ignore[no-untyped-def]
        return self.base.emit_direction(**kwargs)

    def emit_direction_payload(self, **kwargs):  # type: ignore[no-untyped-def]
        return self.base.emit_direction_payload(**kwargs)

    def emit_action_candidate(self, **kwargs):  # type: ignore[no-untyped-def]
        return self.base.emit_action_candidate(**kwargs)

    def emit_governance(self, **kwargs):  # type: ignore[no-untyped-def]
        return self.base.emit_governance(**kwargs)

    def emit_action(
        self,
        action: ActionRecord,
        *,
        metrics=None,
        step_status=None,
        caused_by=None,
    ) -> None:
        extensions = action.extensions
        if "x-action_candidate_id" in extensions and extensions["x-action_candidate_id"] != self.candidate_id:
            raise ValueError("action_candidate_id mismatch for guarded action emission")
        extensions["x-action_candidate_id"] = self.candidate_id
        self.base.emit_action(
            action,
            metrics=metrics,
            step_status=step_status,
            caused_by=self.caused_by,
        )

    def emit_reflect(self, **kwargs):  # type: ignore[no-untyped-def]
        return self.base.emit_reflect(**kwargs)


def _as_legacy_result(result: GovernedResult) -> ActuationResult:
    status = result.status.value
    if result.status is ActuationStatus.BLOCKED:
        status = "vetoed"
    return ActuationResult(
        status=status,
        summary=result.summary,
        metrics=dict(result.metrics),
        reasons=list(result.reasons),
        success=result.status is ActuationStatus.OK,
    )


__all__ = ["GovernedActuator", "ActionCandidateBuilder"]
