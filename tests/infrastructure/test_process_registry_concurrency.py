from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from noesis.domain.process import derive_process_identity
from noesis.infrastructure.process_registry import FileProcessRegistry
from noesis.usecases.process_registry import ProcessRegistryService


def test_allocate_run_index_is_unique_under_concurrency(tmp_path) -> None:
    registry = FileProcessRegistry(tmp_path / "processes")
    service = ProcessRegistryService(registry)
    identity = derive_process_identity(workspace_identity="/tmp/workspace", process_name="alpha")

    def _allocate(i: int) -> int:
        record = service.allocate_run(identity, run_id=f"ep-{i}")
        return record.run_index

    workers = 8
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_allocate, range(workers)))

    assert len(set(results)) == workers
    assert sorted(results) == list(range(1, workers + 1))
