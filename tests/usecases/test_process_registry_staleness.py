from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from noesis.domain.process import derive_process_identity
from noesis.infrastructure.process_registry import FileProcessRegistry
from noesis.usecases.process_registry import ProcessRegistryService, STALE_TTL_SECONDS


def test_process_becomes_stale_after_ttl(tmp_path) -> None:
    registry = FileProcessRegistry(tmp_path / "processes")
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    service = ProcessRegistryService(registry, now=lambda: now)
    identity = derive_process_identity(workspace_identity="/tmp/workspace", process_name="alpha")

    process = service.get_or_create(identity)
    stale_at = now - timedelta(seconds=STALE_TTL_SECONDS + 1)
    stale = replace(
        process,
        status="running",
        last_seen_at=stale_at,
        last_heartbeat_at=stale_at,
        updated_at=stale_at,
    )
    registry.upsert(stale)

    loaded = registry.get(process.process_id)
    assert loaded is not None
    assert service.liveness_status(loaded) == "stale"

    service.heartbeat(process.process_id)
    refreshed = registry.get(process.process_id)
    assert refreshed is not None
    assert service.liveness_status(refreshed) == "running"
