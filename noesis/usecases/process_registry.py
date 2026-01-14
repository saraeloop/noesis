"""Use-case helpers for process registration and lifecycle updates."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable

from noesis.domain.process import Process, ProcessIdentity, ProcessKind, ProcessStatus
from noesis.interfaces.process import ProcessRegistryPort

__all__ = ["ProcessRegistryService"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class ProcessRegistryService:
    """Coordinate process registry updates without leaking persistence details."""

    registry: ProcessRegistryPort
    now: Callable[[], datetime] = _utc_now

    def get_or_create(self, identity: ProcessIdentity, *, kind: ProcessKind = "oneshot") -> Process:
        existing = self.registry.get(identity.process_id)
        if existing is not None:
            return existing
        timestamp = self.now()
        process = Process(
            process_id=identity.process_id,
            process_name=identity.process_name,
            kind=kind,
            status="idle",
            created_at=timestamp,
            last_seen_at=timestamp,
            active_run_id=None,
            last_run_outcome=None,
            run_index=0,
        )
        self.registry.upsert(process)
        return process

    def start_run(self, process_id: str, *, run_id: str) -> Process:
        process = self._require(process_id)
        timestamp = self.now()
        updated = replace(
            process,
            last_seen_at=timestamp,
            active_run_id=run_id,
            status="running",
            run_index=process.run_index + 1,
        )
        self.registry.upsert(updated)
        return updated

    def end_run(
        self,
        process_id: str,
        *,
        run_id: str,
        outcome: str | None,
        status: ProcessStatus = "idle",
    ) -> Process:
        process = self._require(process_id)
        timestamp = self.now()
        active_run_id = None if process.active_run_id == run_id else process.active_run_id
        updated = replace(
            process,
            last_seen_at=timestamp,
            active_run_id=active_run_id,
            last_run_outcome=outcome,
            status=status,
        )
        self.registry.upsert(updated)
        return updated

    def _require(self, process_id: str) -> Process:
        process = self.registry.get(process_id)
        if process is None:
            raise KeyError(f"unknown process_id: {process_id}")
        return process
