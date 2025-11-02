"""
Public event emission helpers.

Provides thin wrappers around the runtime event emitters plus convenience
aliases with shorter verb names.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Dict, Iterable
from warnings import warn

from .runtime.events import (
    act_event as _act_event,
    ensure_act_event as _ensure_act_event,
    interpret_event as _interpret_event,
    last_event_of_phase as _last_event_of_phase,
    observe_event as _observe_event,
    plan_event as _plan_event,
    reflect_event as _reflect_event,
    start_event as _start_event,
    terminate_event as _terminate_event,
)
from .io import events as _events_fn

__all__ = [
    "read",
    "start",
    "observe",
    "interpret",
    "plan",
    "act",
    "reflect",
    "ensure",
    "terminate",
    "last_event_of_phase",
]


def read(episode_id: str, *, stream: bool = False, context: Any | None = None) -> Iterable[Dict[str, Any]]:
    """Return events for an episode."""
    return _events_fn(episode_id, stream=stream, context=context)


def start(*args: Any, **kwargs: Any) -> None:
    """Emit a start event for the episode."""
    _start_event(*args, **kwargs)


def observe(*args: Any, **kwargs: Any) -> None:
    """Emit an observe event for the episode."""
    _observe_event(*args, **kwargs)


def interpret(*args: Any, **kwargs: Any) -> None:
    """Emit an interpret event for the episode."""
    _interpret_event(*args, **kwargs)


def plan(*args: Any, **kwargs: Any) -> None:
    """Emit a plan event for the episode."""
    _plan_event(*args, **kwargs)


def act(*args: Any, **kwargs: Any) -> None:
    """Emit an act event for the episode."""
    _act_event(*args, **kwargs)


def reflect(*args: Any, **kwargs: Any) -> None:
    """Emit a reflect event for the episode."""
    _reflect_event(*args, **kwargs)


def ensure(*args: Any, **kwargs: Any) -> None:
    """Emit the ensure-act event for the episode."""
    _ensure_act_event(*args, **kwargs)


def terminate(*args: Any, **kwargs: Any) -> None:
    """Emit a terminate event for the episode."""
    _terminate_event(*args, **kwargs)


def last_event_of_phase(*args: Any, **kwargs: Any) -> Dict[str, Any] | None:
    """Return the most recent event for the given verb."""
    return _last_event_of_phase(*args, **kwargs)


def _deprecated(name: str, replacement: str):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            warn(
                f"'noesis.events.{name}' is deprecated; use 'noesis.events.{replacement}' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return fn(*args, **kwargs)

        return wrapper

    return decorator


# Backwards compatibility shims with deprecation warnings.
start_event = _deprecated("start_event", "start")(start)
observe_event = _deprecated("observe_event", "observe")(observe)
interpret_event = _deprecated("interpret_event", "interpret")(interpret)
plan_event = _deprecated("plan_event", "plan")(plan)
act_event = _deprecated("act_event", "act")(act)
reflect_event = _deprecated("reflect_event", "reflect")(reflect)
ensure_act_event = _deprecated("ensure_act_event", "ensure")(ensure)
terminate_event = _deprecated("terminate_event", "terminate")(terminate)
