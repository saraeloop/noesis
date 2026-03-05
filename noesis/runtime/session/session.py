"""Concrete NoesisSession implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, MutableMapping, Optional

from noesis.context import RuntimeContext
from noesis.interfaces.config import ConfigPort, ConfigSnapshot
from noesis.intuition import Intuition
from noesis.verification import VerifyInput, normalize_verify

from .models import SessionConfig, DeterminismConfig
from .runner_port import RunnerProtocol, SessionRunRequest
from .threading import SessionLock

__all__ = ["NoesisSession"]


class NoesisSession:
    """Owns runtime config, registered ports, and execution helpers."""

    def __init__(self, *, config: SessionConfig, context: RuntimeContext) -> None:
        self._config = config
        self._context = context
        self._lock = SessionLock()
        self._config_port: ConfigPort = context.config_port

    @property
    def config_snapshot(self) -> ConfigSnapshot:
        return self._config.snapshot

    @property
    def context(self) -> RuntimeContext:
        return self._context

    @property
    def determinism(self) -> DeterminismConfig | None:
        """Expose deterministic instrumentation for callers that need it."""
        return self._config.determinism

    def merge_tags(self, tags: MutableMapping[str, Any] | None) -> dict[str, Any]:
        """Merge tags with the session's defaults."""
        return self._config.merge_tags(tags)

    def configure(self, **overrides: object) -> SessionConfig:
        """Apply config overrides and refresh the stored snapshot."""
        api = getattr(self._config_port, "__api_version__", "config/1.0-rc1")
        port = self._context.require("config", api)
        snapshot = port.set(**overrides)
        self._config = SessionConfig(
            snapshot=snapshot,
            default_tags=self._config.default_tags,
            determinism=self._config.determinism,
        )
        return self._config

    def run(
        self,
        task: str,
        *,
        seed: int = 0,
        intuition: bool | Intuition | None = True,
        tags: Optional[MutableMapping[str, Any]] = None,
        workspace: str | Path | None = None,
        process: str | None = None,
        verify: "VerifyInput" = None,
        runner: RunnerProtocol | None = None,
    ) -> str:
        """Execute a task either through the built-in core or a supplied runner."""
        merged_tags = self._config.merge_tags(tags)
        workspace_path = Path(workspace) if workspace is not None else None
        verify_specs = normalize_verify(verify)
        with self._lock.scoped():
            if runner is not None:
                request = SessionRunRequest(
                    task=task,
                    seed=seed,
                    intuition=intuition,
                    tags=merged_tags,
                    workspace=workspace_path,
                    process=process,
                    verify=verify_specs,
                    process_name=process,
                )
                return runner.run(request, context=self._context)

            from noesis.core import run as core_run

            return core_run(
                task=task,
                seed=seed,
                intuition=intuition,
                tags=merged_tags,
                context=self._context,
                workspace=workspace_path,
                verify=verify_specs,
                determinism=self._config.determinism,
                process_name=process,
            )

    def solve(
        self,
        *,
        using: Any,
        task: str,
        seed: int = 0,
        intuition: bool | Intuition = True,
        tags: Optional[MutableMapping[str, Any]] = None,
        workspace: str | Path | None = None,
        process: str | None = None,
        verify: "VerifyInput" = None,
    ) -> str:
        """Execute a task using a supplied graph/adapter."""
        from noesis.core import run_using as core_run_using

        merged_tags = self._config.merge_tags(tags)
        workspace_path = Path(workspace) if workspace is not None else None
        verify_specs = normalize_verify(verify)
        with self._lock.scoped():
            return core_run_using(
                using=using,
                task=task,
                seed=seed,
                intuition=intuition,
                tags=merged_tags,
                context=self._context,
                workspace=workspace_path,
                verify=verify_specs,
                determinism=self._config.determinism,
                process_name=process,
            )

    def interrupt(
        self,
        run_id: str,
        *,
        reason: str | None = None,
        caused_by: str | None = None,
        workspace: str | Path | None = None,
    ) -> str:
        """Emit a run interruption lifecycle event for an unsealed run."""
        from noesis.core import interrupt as core_interrupt

        workspace_path = Path(workspace) if workspace is not None else None
        with self._lock.scoped():
            return core_interrupt(
                run_id,
                reason=reason,
                caused_by=caused_by,
                context=self._context,
                workspace=workspace_path,
            )

    def checkpoint(
        self,
        run_id: str,
        *,
        caused_by: str | None = None,
        workspace: str | Path | None = None,
    ) -> dict[str, object]:
        """Persist a checkpoint pointer for an unsealed run."""
        from noesis.core import checkpoint as core_checkpoint

        workspace_path = Path(workspace) if workspace is not None else None
        with self._lock.scoped():
            return core_checkpoint(
                run_id,
                caused_by=caused_by,
                context=self._context,
                workspace=workspace_path,
            )

    def resume(
        self,
        run_id: str,
        *,
        checkpoint_id: str,
        caused_by: str | None = None,
        workspace: str | Path | None = None,
    ) -> str:
        """Emit a run resume lifecycle event for an unsealed checkpoint."""
        from noesis.core import resume as core_resume

        workspace_path = Path(workspace) if workspace is not None else None
        with self._lock.scoped():
            return core_resume(
                run_id,
                checkpoint_id=checkpoint_id,
                caused_by=caused_by,
                context=self._context,
                workspace=workspace_path,
            )

    def resume_run(
        self,
        run_id: str,
        *,
        checkpoint_id: str,
        using: Any | None = None,
        caused_by: str | None = None,
        workspace: str | Path | None = None,
        verify: "VerifyInput" = None,
    ) -> str:
        """Resume lifecycle evidence and continue execution on the same run."""
        from noesis.core import resume_run as core_resume_run

        workspace_path = Path(workspace) if workspace is not None else None
        verify_specs = normalize_verify(verify)
        with self._lock.scoped():
            return core_resume_run(
                run_id,
                checkpoint_id=checkpoint_id,
                using=using,
                caused_by=caused_by,
                context=self._context,
                workspace=workspace_path,
                verify=verify_specs,
                determinism=self._config.determinism,
            )

    async def solve_async(
        self,
        *,
        using: Any,
        task: str,
        seed: int = 0,
        intuition: bool | Intuition = True,
        tags: Optional[MutableMapping[str, Any]] = None,
        workspace: str | Path | None = None,
        process: str | None = None,
        verify: "VerifyInput" = None,
    ) -> str:
        """Execute a task using a supplied graph/adapter (async)."""
        from noesis.core import run_using_async as core_run_using_async

        merged_tags = self._config.merge_tags(tags)
        workspace_path = Path(workspace) if workspace is not None else None
        verify_specs = normalize_verify(verify)
        with self._lock.scoped():
            return await core_run_using_async(
                using=using,
                task=task,
                seed=seed,
                intuition=intuition,
                tags=merged_tags,
                context=self._context,
                workspace=workspace_path,
                verify=verify_specs,
                determinism=self._config.determinism,
                process_name=process,
            )

    def with_ports(self, **ports: tuple[Any, str]) -> "NoesisSession":
        """Register additional ports on the underlying runtime context."""
        for name, binding in ports.items():
            provider, api = binding
            self._context.register(name, provider, api=api)
        return self
