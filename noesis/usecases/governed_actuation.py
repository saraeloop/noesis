"""Governed actuation collaborators for canonical episode execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from noesis.domain.action_candidates import ActionCandidate, RedactionSpec
from noesis.domain.planner.interfaces import ActuationResult, Actuator
from noesis.domain.state import NoesisState, PlanStep
from noesis.usecases.actuation.governed_actuator import ActionCandidateBuilder


@dataclass(frozen=True, slots=True)
class EpisodeActuationBindings:
    """Typed actuation collaborators injected into the canonical episode runner."""

    actuator: Actuator
    action_candidate_builder: ActionCandidateBuilder | None = None


@dataclass(slots=True)
class GovernedActionActuator:
    """Execute one governed side effect through the runner's actuation contract."""

    kind: str
    payload: Mapping[str, Any]
    tool_label: str
    executor: Callable[..., Any]
    result: Any | None = None
    error: Exception | None = None
    invoked: bool = False

    def execute(
        self,
        *,
        plan: Sequence[PlanStep],
        request: Any,
        state: NoesisState,
        event_bus: Any,
    ) -> ActuationResult:
        self.invoked = True
        summary: str | None = None
        status = "ok"
        success = True
        reasons: list[str] = []
        try:
            self.result = _invoke_executor(self.executor, self.payload)
            summary = str(self.result)[:400]
            reasons.append("executor_ok")
        except Exception as exc:  # noqa: BLE001
            self.error = exc
            status = "error"
            success = False
            summary = str(exc)
            reasons.append("executor_error")

        step_id = plan[-1].id if plan else None
        action = state.record_action(
            kind=self.kind,
            tool=self.tool_label,
            input_excerpt=governed_input_excerpt(goal=request.goal, payload=self.payload),
            result_status="ok" if success else "error",
            step_id=step_id,
        )
        event_bus.emit_action(action)

        return ActuationResult(
            status=status,
            summary=summary,
            metrics={"success": 1.0 if success else 0.0},
            reasons=reasons,
            success=success,
        )


@dataclass(slots=True)
class GovernedActionCandidateFactory(ActionCandidateBuilder):
    """Build deterministic governance candidates for governed side effects."""

    state_hash_resolver: Callable[[], str]
    kind: str
    payload: Mapping[str, Any]
    provenance: Mapping[str, Any] | None
    risk_tags: tuple[str, ...] | None
    redaction: Mapping[str, Any] | None

    def build(
        self,
        *,
        plan: Sequence[PlanStep],
        request: Any,
        state: NoesisState,
    ) -> ActionCandidate:
        redaction_spec = parse_governed_redaction(self.redaction)
        step = plan[-1] if plan else None
        step_provenance: dict[str, Any] = {}
        if step is not None:
            step_provenance["plan_step_id"] = step.id
            step_provenance["plan_step_kind"] = getattr(step.kind, "value", str(step.kind))
        merged_provenance = dict(self.provenance or {})
        merged_provenance.update(step_provenance)
        return ActionCandidate(
            id=None,
            kind=self.kind,
            payload=dict(self.payload),
            state_ref="state.json",
            state_hash=self.state_hash_resolver(),
            redaction=redaction_spec,
            provenance=merged_provenance or None,
            risk_tags=tuple(self.risk_tags or ()),
        )


def build_governed_actuation_bindings(
    *,
    kind: str,
    payload: Mapping[str, Any],
    tool_label: str,
    executor: Callable[..., Any],
    state_hash_resolver: Callable[[], str],
    provenance: Mapping[str, Any] | None,
    risk_tags: Sequence[str] | None,
    redaction: Mapping[str, Any] | None,
) -> EpisodeActuationBindings:
    """Create the governed actuation bindings for a canonical runtime episode."""

    payload_copy = dict(payload)
    return EpisodeActuationBindings(
        actuator=GovernedActionActuator(
            kind=kind,
            payload=payload_copy,
            tool_label=tool_label,
            executor=executor,
        ),
        action_candidate_builder=GovernedActionCandidateFactory(
            state_hash_resolver=state_hash_resolver,
            kind=kind,
            payload=payload_copy,
            provenance=dict(provenance) if provenance else None,
            risk_tags=tuple(risk_tags) if risk_tags else None,
            redaction=dict(redaction) if redaction else None,
        ),
    )


def parse_governed_redaction(redaction: Mapping[str, Any] | None) -> RedactionSpec:
    """Normalize governed-action redaction settings into a RedactionSpec."""

    if redaction is None:
        return RedactionSpec(
            mode="hash_only",
            policy_id="redact.default",
            policy_version="1.0.0",
            field_rules={},
        )
    return RedactionSpec(
        mode=str(redaction.get("mode", "hash_only")),
        policy_id=str(redaction.get("policy_id", "redact.default")),
        policy_version=str(redaction.get("policy_version", "1.0.0")),
        field_rules=dict(redaction.get("field_rules") or {}),
    )


def governed_input_excerpt(*, goal: str, payload: Mapping[str, Any]) -> str:
    """Produce a compact, stable input excerpt for governed action events."""

    for key in ("command", "cmd", "input_excerpt"):
        if key in payload:
            return str(payload.get(key, ""))[:120]
    return str(goal)[:120]


def _invoke_executor(executor: Callable[..., Any], payload: Mapping[str, Any]) -> Any:
    try:
        return executor(**dict(payload))
    except TypeError:
        return executor(payload)
