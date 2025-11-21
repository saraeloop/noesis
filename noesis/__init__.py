from __future__ import annotations

from importlib import import_module
from typing import Any, Dict, Optional
from warnings import warn

from .trace.schema import SUMMARY_SCHEMA_VERSION
from .intuition import Intuition
from .loader import GraphSource
from .runtime.session import (
    DefaultSessionProvider,
    NoesisSession,
    SessionBuilder,
)

# Package metadata
__version__ = "1.0.0"
__schema_version__ = SUMMARY_SCHEMA_VERSION

# Legacy config access (kept for compatibility)
from .context import get_config_port  # re-exported via deprecated alias
from . import context as _context, events as _events, learn as _learn, summary as _summary

_SESSION_PROVIDER = DefaultSessionProvider()


def session_provider() -> DefaultSessionProvider:
    """Expose the global session provider for advanced integrations."""
    return _SESSION_PROVIDER


def create_session(builder: SessionBuilder | None = None) -> NoesisSession:
    """Build a new session (factory for tests, services, or CLIs)."""
    return (builder or SessionBuilder.from_env()).build()


def _current_session() -> NoesisSession:
    return _SESSION_PROVIDER.current()


def run(
    task: str,
    *,
    seed: int = 0,
    intuition: bool | Intuition | None = True,
    tags: Optional[Dict[str, Any]] = None,
    context: Any | None = None,
) -> str:
    """Execute a task using the default session (planner derived from config)."""
    if context is not None:
        from .core import run as core_run

        return core_run(
            task=task,
            seed=seed,
            intuition=intuition,
            tags=tags,
            context=context,
        )
    return _current_session().run(
        task,
        seed=seed,
        intuition=intuition,
        tags=tags,
    )


def solve(
    task: str,
    *,
    using: GraphSource,
    seed: int = 0,
    intuition: bool | Intuition | None = True,
    tags: Optional[Dict[str, Any]] = None,
    context: Any | None = None,
) -> str:
    """Execute a task using an explicit graph/adapter."""
    if context is not None:
        from .core import run_using as core_run_using

        return core_run_using(
            using=using,
            task=task,
            seed=seed,
            intuition=intuition,
            tags=tags,
            context=context,
        )
    return _current_session().solve(
        using=using,
        task=task,
        seed=seed,
        intuition=intuition,
        tags=tags,
    )


def set(*, context: Any | None = None, **overrides: object) -> None:
    """
    Apply config overrides for either a provided runtime context or the default session.
    """
    if context is not None:
        from .core import set as core_set

        core_set(context=context, **overrides)
        return
    _current_session().configure(**overrides)

def get() -> dict[str, Any]:
    """Public accessor returning a mapping of the current runtime configuration."""
    return _current_session().config_snapshot.to_mapping()

summary = _summary
events = _events
context = _context
learn = _learn

__all__ = (
    "run",
    "solve",
    "set",
    "get",
    "create_session",
    "session_provider",
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
