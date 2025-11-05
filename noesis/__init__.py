from __future__ import annotations

from importlib import import_module
from typing import Any
from warnings import warn

from .trace.schema import SUMMARY_SCHEMA_VERSION

# Package metadata
__version__ = "0.9.5"
__schema_version__ = SUMMARY_SCHEMA_VERSION

# Core execution API
from .core import run, solve, set
from .context import get_config_port  # re-exported via deprecated alias
from . import context as _context, events as _events, learn as _learn, summary as _summary


def get() -> dict[str, Any]:
    """Public accessor returning a mapping of the current runtime configuration."""
    return get_config_port().get().to_mapping()

summary = _summary
events = _events
context = _context
learn = _learn

__all__ = (
    "run",
    "solve",
    "set",
    "get",
    "summary",
    "events",
    "context",
    "learn",
)

_LEGACY_REDIRECTS = {
    # context helpers
    "RuntimeContext": "noesis.context:RuntimeContext",
    "create_runtime_context": "noesis.context:create_runtime_context",
    "create_context": "noesis.context:create_runtime_context",
    "get_context": "noesis.context:get_context",
    "set_context": "noesis.context:set_context",
    "get_config_port": "noesis.context:get_config_port",
    "set_config_port": "noesis.context:set_config_port",
    "get_config_snapshot": "noesis.context:get_config_snapshot",
    # execution helpers
    "run_using": "noesis.core:run_using",
    "list_runs": "noesis.io:list_runs",
    "paths": "noesis.io:paths",
    # cognition helpers
    "Intuition": "noesis.intuition:Intuition",
    "DirectedIntuition": "noesis.direction:DirectedIntuition",
    "NoesisVeto": "noesis.exceptions:NoesisVeto",
    "MinimalPlanner": "noesis.domain.planner.minimal:MinimalPlanner",
    # module shortcuts
    "episode": "noesis.episode",
    "insight": "noesis.insight",
}


def __getattr__(name: str) -> Any:
    target = _LEGACY_REDIRECTS.get(name)
    if target is None:
        raise AttributeError(f"module 'noesis' has no attribute '{name}'")

    module_path, sep, attribute = target.partition(":")
    module = import_module(module_path)
    warn_target = attribute or module_path
    warn(
        f"'noesis.{name}' is deprecated; import '{warn_target}' directly instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return getattr(module, attribute) if attribute else module


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(_LEGACY_REDIRECTS))
