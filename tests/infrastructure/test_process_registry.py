from __future__ import annotations

from noesis.domain.process import derive_process_identity
from noesis.infrastructure.process_registry import FileProcessRegistry
from noesis.usecases.process_registry import ProcessRegistryService


def test_process_registry_round_trip(tmp_path) -> None:
    registry = FileProcessRegistry(tmp_path / "processes")
    identity = derive_process_identity(workspace_identity="/tmp/workspace", process_name="alpha")
    service = ProcessRegistryService(registry)

    process = service.get_or_create(identity)
    service.start_run(process.process_id, run_id="ep-one")
    service.end_run(process.process_id, run_id="ep-one", outcome="success", status="idle")

    fresh_registry = FileProcessRegistry(tmp_path / "processes")
    loaded = fresh_registry.get(process.process_id)

    assert loaded is not None
    assert loaded.process_id == process.process_id
    assert loaded.process_name == "alpha"
    assert loaded.last_run_outcome == "success"


def test_process_run_index_increments(tmp_path) -> None:
    registry = FileProcessRegistry(tmp_path / "processes")
    identity = derive_process_identity(workspace_identity="/tmp/workspace", process_name="alpha")
    service = ProcessRegistryService(registry)

    process = service.get_or_create(identity)
    first = service.start_run(process.process_id, run_id="ep-one")
    assert first.run_index == 1
    service.end_run(process.process_id, run_id="ep-one", outcome="success", status="idle")

    second = service.start_run(process.process_id, run_id="ep-two")
    assert second.run_index == 2
