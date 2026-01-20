from __future__ import annotations

from noesis.domain.process import derive_process_identity
from noesis.infrastructure.process_registry import FileProcessRegistry
from noesis.usecases.process_registry import ProcessRegistryService


def test_registry_ignores_partial_writes(tmp_path) -> None:
    registry = FileProcessRegistry(tmp_path / "processes")
    service = ProcessRegistryService(registry)
    identity = derive_process_identity(workspace_identity="/tmp/workspace", process_name="alpha")
    process = service.get_or_create(identity)

    index_path = (tmp_path / "processes") / "index.json"
    index_path.unlink()

    bad_path = (tmp_path / "processes") / "corrupt.json"
    bad_path.write_text("{not-json", encoding="utf-8")

    processes = registry.list()
    assert any(item.process_id == process.process_id for item in processes)
