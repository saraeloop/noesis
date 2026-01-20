"""Use-case helpers for process registration and lifecycle updates."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Callable

from noesis.domain.process import Process, ProcessIdentity, ProcessKind, ProcessStatus
from noesis.interfaces.process import ProcessRegistryPort
from noesis.runtime.utils import now as now_str, parse_iso8601

__all__ = ["ProcessRegistryService", "STALE_TTL_SECONDS", "derive_liveness_status"]

STALE_TTL_SECONDS = 300


def _utc_now() -> datetime:
    parsed = parse_iso8601(now_str())
    if parsed is not None:
        return parsed
    return datetime.now(timezone.utc)


def derive_liveness_status(
    process: Process,
    *,
    now: datetime,
    stale_ttl: timedelta,
) -> ProcessStatus:
    if process.status in {"idle", "error"}:
        return process.status
    delta = now - process.last_heartbeat_at
    if delta > stale_ttl:
        return "stale"
    return "running"


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
            last_heartbeat_at=timestamp,
            updated_at=timestamp,
            active_run_id=None,
            last_run_outcome=None,
            run_index=0,
            next_run_index=1,
        )
        self.registry.upsert(process)
        return process

    def start_run(self, process_id: str, *, run_id: str) -> Process:
        process = self._require(process_id)
        return self.registry.allocate_run(
            process_id=process.process_id,
            process_name=process.process_name,
            kind=process.kind,
            run_id=run_id,
        )

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
            last_heartbeat_at=timestamp,
            updated_at=timestamp,
            active_run_id=active_run_id,
            last_run_outcome=outcome,
            status=status,
        )
        self.registry.upsert(updated)
        return updated

    def allocate_run(self, identity: ProcessIdentity, *, run_id: str, kind: ProcessKind = "oneshot") -> Process:
        return self.registry.allocate_run(
            process_id=identity.process_id,
            process_name=identity.process_name,
            kind=kind,
            run_id=run_id,
        )

    def heartbeat(self, process_id: str) -> Process:
        return self.registry.heartbeat(process_id)

    def liveness_status(self, process: Process, *, stale_ttl_seconds: int = STALE_TTL_SECONDS) -> ProcessStatus:
        return derive_liveness_status(
            process,
            now=self.now(),
            stale_ttl=timedelta(seconds=stale_ttl_seconds),
        )

    def _require(self, process_id: str) -> Process:
        process = self.registry.get(process_id)
        if process is None:
            raise KeyError(f"unknown process_id: {process_id}")
        return process
