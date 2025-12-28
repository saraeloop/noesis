"""Canonical faculty hook ordering."""

from __future__ import annotations

from typing import Sequence, Tuple

FACULTY_HOOK_ORDER: Tuple[str, ...] = (
    "observe",
    "intuition",
    "interpret",
    "plan",
    "direction",
    "governance",
    "act",
    "reflect",
    "learn",
    "terminate",
    "insight",
)

_ORDER_INDEX = {phase: index for index, phase in enumerate(FACULTY_HOOK_ORDER)}
_ALIASES = {
    "governance.pre_act": "governance",
    "finalize": "insight",
}


def validate_hook_sequence(phases: Sequence[str]) -> None:
    """
    Ensure that observed phases respect the canonical hook order.

    Extra phases are ignored, but any canonical phase that appears must respect
    the monotonic ordering with the optional `governance` occurring before `act`.
    """
    last_position = -1
    first_occurrence: dict[str, int] = {}
    for idx, phase in enumerate(phases):
        normalized = _ALIASES.get(phase, phase)
        if normalized in _ORDER_INDEX and normalized not in first_occurrence:
            first_occurrence[normalized] = idx

    last_position = -1
    for canonical in FACULTY_HOOK_ORDER:
        if canonical not in first_occurrence:
            continue
        position = first_occurrence[canonical]
        if position < last_position:
            raise ValueError(f"Phase '{canonical}' occurred out of order.")
        last_position = position

    pre_act = first_occurrence.get("governance")
    act = first_occurrence.get("act")
    if pre_act is not None and act is not None and pre_act > act:
        raise ValueError("governance must precede act in the hook sequence.")


__all__ = ["FACULTY_HOOK_ORDER", "validate_hook_sequence"]
