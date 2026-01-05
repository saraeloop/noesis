"""
Lightweight invariants for trace validation.

These checks are advisory until integrated into diagnostics/CI. They avoid
side effects and operate on in-memory event payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from noesis.domain.action_candidates import ACTION_CANDIDATE_SCHEMA_VERSION
from noesis.diagnostics.validators import is_valid_sha256_state_hash


@dataclass(slots=True)
class InvariantViolation:
    """Represents a single trace invariant violation."""

    event_id: str
    detail: str


def check_action_candidate_invariants(
    events: Iterable[Mapping[str, object]],
) -> list[InvariantViolation]:
    """
    Verify action candidate invariants for side-effectful act events.

    Rules:
    - If an act payload includes action_candidate_id, a prior action_candidate
      event with that id must exist.
    - If an act payload includes tool/adapter, action_candidate_id should be present.
    """
    violations: list[InvariantViolation] = []
    seen_candidates: set[str] = set()
    for event in events:
        phase = event.get("phase")
        payload = event.get("payload")
        event_id = str(event.get("id", "unknown"))
        if phase == "action_candidate" and isinstance(payload, dict):
            candidate_id = payload.get("action_candidate_id")
            if isinstance(candidate_id, str):
                seen_candidates.add(candidate_id)
            else:
                violations.append(
                    InvariantViolation(
                        event_id=event_id,
                        detail="action_candidate missing action_candidate_id",
                    )
                )
            schema_version = payload.get("schema_version")
            if schema_version != ACTION_CANDIDATE_SCHEMA_VERSION:
                violations.append(
                    InvariantViolation(
                        event_id=event_id,
                        detail="action_candidate schema_version mismatch",
                    )
                )
            state_hash = payload.get("state_hash")
            if isinstance(state_hash, str) and not is_valid_sha256_state_hash(state_hash):
                violations.append(
                    InvariantViolation(
                        event_id=event_id,
                        detail="action_candidate state_hash invalid",
                    )
                )
        if phase == "act" and isinstance(payload, dict):
            candidate_id = payload.get("action_candidate_id")
            has_side_effect_marker = any(key in payload for key in ("tool", "adapter"))
            if has_side_effect_marker and not isinstance(candidate_id, str):
                violations.append(
                    InvariantViolation(
                        event_id=event_id,
                        detail="side-effect act missing action_candidate_id",
                    )
                )
            if isinstance(candidate_id, str) and candidate_id not in seen_candidates:
                violations.append(
                    InvariantViolation(
                        event_id=event_id,
                        detail="act references unknown action_candidate_id",
                    )
                )
    return violations


__all__ = ["InvariantViolation", "check_action_candidate_invariants"]
