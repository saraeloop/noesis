from __future__ import annotations

from importlib import import_module
from pathlib import Path
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
from .runtime.determinism import DeterministicClock, DeterministicRNG

# Promoted public APIs (first-class exports)
from .direction import DirectedIntuition
from .exceptions import NoesisVeto
from .io import list_runs, last, paths
from .api.governed_act import governed_act
from .verification import (
    VerifyInput,
    VerifySpec,
    file_contains,
    file_exists,
    no_modifications,
    normalize_verify,
    only_modified,
)

# Package metadata
__version__ = "v1.0.0"
__schema_version__ = SUMMARY_SCHEMA_VERSION

# Submodule aliases (public)
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
    workspace: str | Path | None = None,
    process: str | None = None,
    verify: VerifyInput = None,
) -> str:
    """Execute a task using the default session (planner derived from config)."""
    workspace_path = Path(workspace) if workspace is not None else None
    verify_spec = normalize_verify(verify)
    if context is not None:
        from .core import run as core_run

        return core_run(
            task=task,
            seed=seed,
            intuition=intuition,
            tags=tags,
            context=context,
            workspace=workspace_path,
            verify=verify_spec,
            process_name=process,
        )
    return _current_session().run(
        task,
        seed=seed,
        intuition=intuition,
        tags=tags,
        workspace=workspace_path,
        verify=verify_spec,
        process=process,
    )


def solve(
    task: str,
    *,
    using: GraphSource,
    seed: int = 0,
    intuition: bool | Intuition | None = True,
    tags: Optional[Dict[str, Any]] = None,
    context: Any | None = None,
    workspace: str | Path | None = None,
    process: str | None = None,
    verify: VerifyInput = None,
) -> str:
    """Execute a task using an explicit graph/adapter."""
    workspace_path = Path(workspace) if workspace is not None else None
    verify_spec = normalize_verify(verify)
    if context is not None:
        from .core import run_using as core_run_using

        return core_run_using(
            using=using,
            task=task,
            seed=seed,
            intuition=intuition,
            tags=tags,
            context=context,
            workspace=workspace_path,
            process_name=process,
            verify=verify_spec,
        )
    return _current_session().solve(
        using=using,
        task=task,
        seed=seed,
        intuition=intuition,
        tags=tags,
        workspace=workspace_path,
        process=process,
        verify=verify_spec,
    )


def interrupt(
    episode_id: str,
    *,
    reason: str | None = None,
    caused_by: str | None = None,
    context: Any | None = None,
    workspace: str | Path | None = None,
) -> str:
    """Emit a run interruption lifecycle event for an unsealed run."""
    workspace_path = Path(workspace) if workspace is not None else None
    if context is not None:
        from .core import interrupt as core_interrupt

        return core_interrupt(
            episode_id,
            reason=reason,
            caused_by=caused_by,
            context=context,
            workspace=workspace_path,
        )
    return _current_session().interrupt(
        episode_id,
        reason=reason,
        caused_by=caused_by,
        workspace=workspace_path,
    )


def checkpoint(
    episode_id: str,
    *,
    caused_by: str | None = None,
    context: Any | None = None,
    workspace: str | Path | None = None,
) -> dict[str, object]:
    """Create a deterministic checkpoint pointer for an unsealed run."""
    workspace_path = Path(workspace) if workspace is not None else None
    if context is not None:
        from .core import checkpoint as core_checkpoint

        return core_checkpoint(
            episode_id,
            caused_by=caused_by,
            context=context,
            workspace=workspace_path,
        )
    return _current_session().checkpoint(
        episode_id,
        caused_by=caused_by,
        workspace=workspace_path,
    )


def resume(
    episode_id: str,
    *,
    checkpoint_id: str,
    caused_by: str | None = None,
    context: Any | None = None,
    workspace: str | Path | None = None,
) -> str:
    """Emit a run resume lifecycle event for an unsealed checkpoint."""
    workspace_path = Path(workspace) if workspace is not None else None
    if context is not None:
        from .core import resume as core_resume

        return core_resume(
            episode_id,
            checkpoint_id=checkpoint_id,
            caused_by=caused_by,
            context=context,
            workspace=workspace_path,
        )
    return _current_session().resume(
        episode_id,
        checkpoint_id=checkpoint_id,
        caused_by=caused_by,
        workspace=workspace_path,
    )


def resume_run(
    episode_id: str,
    *,
    checkpoint_id: str,
    using: GraphSource | None = None,
    caused_by: str | None = None,
    context: Any | None = None,
    workspace: str | Path | None = None,
    verify: VerifyInput = None,
) -> str:
    """Resume a run from checkpoint and continue execution on the same run ID."""
    workspace_path = Path(workspace) if workspace is not None else None
    verify_spec = normalize_verify(verify)
    if context is not None:
        from .core import resume_run as core_resume_run

        return core_resume_run(
            episode_id,
            checkpoint_id=checkpoint_id,
            using=using,
            caused_by=caused_by,
            context=context,
            workspace=workspace_path,
            verify=verify_spec,
        )
    return _current_session().resume_run(
        episode_id,
        checkpoint_id=checkpoint_id,
        using=using,
        caused_by=caused_by,
        workspace=workspace_path,
        verify=verify_spec,
    )


async def solve_async(
    task: str,
    *,
    using: GraphSource,
    seed: int = 0,
    intuition: bool | Intuition | None = True,
    tags: Optional[Dict[str, Any]] = None,
    context: Any | None = None,
    workspace: str | Path | None = None,
    process: str | None = None,
    verify: VerifyInput = None,
) -> str:
    """Execute a task using an explicit graph/adapter (async)."""
    workspace_path = Path(workspace) if workspace is not None else None
    verify_spec = normalize_verify(verify)
    if context is not None:
        from .core import solve_async as core_solve_async

        return await core_solve_async(
            task=task,
            using=using,
            seed=seed,
            intuition=intuition,
            tags=tags,
            context=context,
            workspace=workspace_path,
            process_name=process,
            verify=verify_spec,
        )
    return await _current_session().solve_async(
        using=using,
        task=task,
        seed=seed,
        intuition=intuition,
        tags=tags,
        workspace=workspace_path,
        process=process,
        verify=verify_spec,
    )


def set(*, context: Any | None = None, **overrides: object) -> None:
    """
    Apply config overrides for either a provided runtime context or the default session.
    """
    from .runtime.actuation_registry import apply_actuation_overrides

    overrides = apply_actuation_overrides(overrides)
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
    # Core execution
    "run",
    "solve",
    "solve_async",
    "interrupt",
    "checkpoint",
    "resume",
    "resume_run",
    "set",
    "get",
    "governed_act",
    # Session management
    "create_session",
    "session_provider",
    "NoesisSession",
    "SessionBuilder",
    "DefaultSessionProvider",
    # Determinism
    "DeterministicClock",
    "DeterministicRNG",
    # Policy authoring
    "DirectedIntuition",
    "Intuition",
    "NoesisVeto",
    # Verification helpers
    "VerifyInput",
    "VerifySpec",
    "file_contains",
    "file_exists",
    "no_modifications",
    "normalize_verify",
    "only_modified",
    # Read/introspection API
    "list_runs",
    "last",
    "paths",
    # Submodules
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
    if attribute:
        import_hint = f"from {module_path} import {attribute}"
    else:
        import_hint = f"import {module_path}"
    warn(
        f"'noesis.{name}' is deprecated; use '{import_hint}' instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return getattr(module, attribute) if attribute else module


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(_LEGACY_REDIRECTS))
