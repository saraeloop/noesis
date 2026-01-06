"""
Runtime registry for governed actuation executors and governance overrides.

This module keeps non-config runtime hooks (executors, custom governors) out of
the domain/config layers while allowing public shims to configure them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from noesis.domain.faculties.governance import PreActGovernor

Executor = Callable[..., Any]

_ACTUATION_KEYS = frozenset({"shell_executor", "adapter_executor", "governance_policy"})


@dataclass(slots=True)
class ActuationRegistry:
    """Holds executors used by the governed act boundary."""

    shell_executor: Executor | None = None
    adapter_executor: Executor | None = None
    governance_policy: PreActGovernor | None = None


_REGISTRY = ActuationRegistry()


def apply_actuation_overrides(overrides: Mapping[str, object]) -> dict[str, object]:
    """
    Apply runtime-only overrides and return the remaining config overrides.
    """
    if not overrides:
        return {}
    remaining = dict(overrides)
    for key in _ACTUATION_KEYS:
        if key in remaining:
            value = remaining.pop(key)
            _set_registry_value(key, value)
    return remaining


def get_actuation_registry() -> ActuationRegistry:
    """Return the current actuation registry."""
    return _REGISTRY


def _set_registry_value(key: str, value: object) -> None:
    if key == "shell_executor":
        _REGISTRY.shell_executor = _require_executor(value, key)
        return
    if key == "adapter_executor":
        _REGISTRY.adapter_executor = _require_executor(value, key)
        return
    if key == "governance_policy":
        _REGISTRY.governance_policy = _require_governor(value, key)
        return
    raise ValueError(f"Unsupported actuation override: {key}")


def _require_executor(value: object, key: str) -> Executor | None:
    if value is None:
        return None
    if callable(value):
        return value
    raise ValueError(f"{key} must be callable or None")


def _require_governor(value: object, key: str) -> PreActGovernor | None:
    if value is None:
        return None
    if isinstance(value, PreActGovernor):
        return value
    raise ValueError(f"{key} must be a PreActGovernor instance or None")


__all__ = ["ActuationRegistry", "apply_actuation_overrides", "get_actuation_registry"]
