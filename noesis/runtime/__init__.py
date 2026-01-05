"""Runtime helper facades."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .config_provider import RuntimeContext, create_runtime_context, get_context, set_context
from .utils import now

__all__ = [
    "action_candidate_event",
    "act_event",
    "direction_event",
    "ensure_act_event",
    "governance_event",
    "interpret_event",
    "observe_event",
    "plan_event",
    "reflect_event",
    "start_event",
    "terminate_event",
    "finalize_summary",
    "now",
    "RuntimeContext",
    "create_runtime_context",
    "get_context",
    "set_context",
]


def __getattr__(name: str) -> Any:
    """
    Lazy-load event and summary helpers to avoid import-time cycles.
    """
    if name in {
        "action_candidate_event",
        "act_event",
        "direction_event",
        "ensure_act_event",
        "governance_event",
        "interpret_event",
        "observe_event",
        "plan_event",
        "reflect_event",
        "start_event",
        "terminate_event",
    }:
        mod = import_module("noesis.runtime.events")
        return getattr(mod, name)
    if name == "finalize_summary":
        mod = import_module("noesis.runtime.summary")
        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
