"""
Default action candidate builder for governed actuation.

Builds deterministic action candidates from the current episode context without
performing I/O or mutating state.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import hashlib
from typing import Any, Mapping, Sequence

from noesis.domain.action_candidates import ActionCandidate, RedactionSpec
from noesis.domain.planner.interfaces import EpisodeRequest
from noesis.domain.state import NoesisState, PlanStep
from noesis.usecases.actuation.governed_actuator import ActionCandidateBuilder

_DEFAULT_REDACTION = RedactionSpec(
    mode="hash_only",
    policy_id="redact.default",
    policy_version="1.0.0",
    field_rules={},
)


@dataclass(slots=True)
class DefaultActionCandidateBuilder(ActionCandidateBuilder):
    """Constructs action candidates for adapter-backed execution."""

    redaction: RedactionSpec = _DEFAULT_REDACTION

    def build(
        self,
        *,
        plan: Sequence[PlanStep],
        request: EpisodeRequest,
        state: NoesisState,
    ) -> ActionCandidate:
        step = plan[-1] if plan else None
        payload: dict[str, Any] = {
            "adapter_label": request.adapter_label,
            "goal": request.goal,
        }
        if step:
            payload["plan_step_id"] = step.id
            payload["plan_step_kind"] = step.kind.value
            payload["plan_step_description"] = step.description
        provenance: Mapping[str, Any] | None = None
        if step:
            provenance = {"plan_step_id": step.id, "adapter": request.adapter_label}
        return ActionCandidate(
            id=None,
            kind="adapter",
            payload=payload,
            state_ref="state.json",
            state_hash=_hash_state(request=request, plan=plan, state=state),
            redaction=self.redaction,
            provenance=provenance,
            risk_tags=(),
        )


def _hash_state(
    *,
    request: EpisodeRequest,
    plan: Sequence[PlanStep],
    state: NoesisState,
) -> str:
    snapshot = {
        "episode_id": state.episode_id,
        "seed": state.seed,
        "task": state.task,
        "adapter_label": request.adapter_label,
        "plan": [
            {"id": step.id, "kind": step.kind.value, "description": step.description}
            for step in plan
        ],
    }
    canonical = _canonical_dumps(snapshot).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    return f"sha256:{digest}"


def _canonical_dumps(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


__all__ = ["DefaultActionCandidateBuilder"]
