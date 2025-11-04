"""
Public event emission helpers.

Provides thin wrappers around the runtime event emitters plus convenience
aliases with shorter verb names.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable

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
    direction_event as _direction_event,
)
from .io import events as _events_fn
from .deprecated import emit_legacy_warning, legacy_shims_enabled

__all__ = [
    "read",
    "start",
    "observe",
    "interpret",
    "plan",
    "act",
    "reflect",
    "direction",
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


def direction(
    run_dir: Any,
    episode_id: str,
    payload: Dict[str, Any],
    *,
    agent: str = "system",
    caused_by: str | None = None,
    metrics: Dict[str, Any] | None = None,
) -> None:
    """Emit a direction (policy) event for the episode."""
    _direction_event(
        run_dir,
        episode_id,
        payload,
        agent=agent,
        caused_by=caused_by,
        metrics=metrics,
    )


def ensure(*args: Any, **kwargs: Any) -> None:
    """Emit the ensure-act event for the episode."""
    _ensure_act_event(*args, **kwargs)


def terminate(*args: Any, **kwargs: Any) -> None:
    """Emit a terminate event for the episode."""
    _terminate_event(*args, **kwargs)


def last_event_of_phase(*args: Any, **kwargs: Any) -> Dict[str, Any] | None:
    """Return the most recent event for the given verb."""
    return _last_event_of_phase(*args, **kwargs)


if legacy_shims_enabled():
    def start_event(*args: Any, **kwargs: Any) -> None:
        emit_legacy_warning("noesis.events.start_event")
        start(*args, **kwargs)

    def observe_event(*args: Any, **kwargs: Any) -> None:
        emit_legacy_warning("noesis.events.observe_event")
        observe(*args, **kwargs)

    def interpret_event(*args: Any, **kwargs: Any) -> None:
        emit_legacy_warning("noesis.events.interpret_event")
        interpret(*args, **kwargs)

    def plan_event(*args: Any, **kwargs: Any) -> None:
        emit_legacy_warning("noesis.events.plan_event")
        plan(*args, **kwargs)

    def act_event(*args: Any, **kwargs: Any) -> None:
        emit_legacy_warning("noesis.events.act_event")
        act(*args, **kwargs)

    def reflect_event(*args: Any, **kwargs: Any) -> None:
        emit_legacy_warning("noesis.events.reflect_event")
        reflect(*args, **kwargs)

    def direction_event(*args: Any, **kwargs: Any) -> None:
        emit_legacy_warning("noesis.events.direction_event")
        direction(*args, **kwargs)

    def ensure_act_event(*args: Any, **kwargs: Any) -> None:
        emit_legacy_warning("noesis.events.ensure_act_event")
        ensure(*args, **kwargs)

    def terminate_event(*args: Any, **kwargs: Any) -> None:
        emit_legacy_warning("noesis.events.terminate_event")
        terminate(*args, **kwargs)

    __all__ += [
        "start_event",
        "observe_event",
        "interpret_event",
        "plan_event",
        "act_event",
        "reflect_event",
        "direction_event",
        "ensure_act_event",
        "terminate_event",
    ]
