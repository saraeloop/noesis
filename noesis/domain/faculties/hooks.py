"""Canonical faculty hook ordering."""

from __future__ import annotations

from typing import Sequence, Tuple

FACULTY_HOOK_ORDER: Tuple[str, ...] = (
    "observe",
    "interpret",
    "plan",
    "direction",
    "governance.pre_act",
    "act",
    "reflect",
    "finalize",
)

_ORDER_INDEX = {phase: index for index, phase in enumerate(FACULTY_HOOK_ORDER)}


def validate_hook_sequence(phases: Sequence[str]) -> None:
    """
    Ensure that observed phases respect the canonical hook order.

    Extra phases are ignored, but any canonical phase that appears must respect
    the monotonic ordering with the optional `governance.pre_act` occurring
    before the first `act`.
    """
    last_position = -1
    first_occurrence: dict[str, int] = {}
    for idx, phase in enumerate(phases):
        if phase in _ORDER_INDEX and phase not in first_occurrence:
            first_occurrence[phase] = idx

    last_position = -1
    for canonical in FACULTY_HOOK_ORDER:
        if canonical not in first_occurrence:
            continue
        position = first_occurrence[canonical]
        if position < last_position:
            raise ValueError(f"Phase '{canonical}' occurred out of order.")
        last_position = position

    pre_act = first_occurrence.get("governance.pre_act")
    act = first_occurrence.get("act")
    if pre_act is not None and act is not None and pre_act > act:
        raise ValueError("governance.pre_act must precede act in the hook sequence.")


__all__ = ["FACULTY_HOOK_ORDER", "validate_hook_sequence"]
