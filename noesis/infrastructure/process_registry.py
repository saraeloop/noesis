"""Filesystem-backed process registry."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence
import json

from noesis.domain.process import PROCESS_SCHEMA_VERSION, Process, ProcessKind
from noesis.interfaces.process import ProcessRegistryPort
from noesis.runtime.serialization import atomic_write_json
from noesis.infrastructure.locking import file_lock
from noesis.runtime.utils import now as now_str, parse_iso8601

INDEX_SCHEMA_VERSION = "process_registry/1.0"
INDEX_FILE_NAME = "index.json"

__all__ = ["FileProcessRegistry", "FileProcessRegistryFactory", "list_processes"]


def _utc_now() -> datetime:
    parsed = parse_iso8601(now_str())
    if parsed is not None:
        return parsed
    return datetime.now(timezone.utc)


def _parse_json(path: Path) -> dict[str, object] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@dataclass(slots=True)
class FileProcessRegistry(ProcessRegistryPort):
    """Store process records as JSON files plus a lightweight index."""

    root: Path
    now: Callable[[], datetime] = _utc_now

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, process_id: str) -> Process | None:
        path = self._process_path(process_id)
        payload = _parse_json(path)
        if not isinstance(payload, dict):
            return None
        return Process.from_dict(payload)

    def get_by_name(self, process_name: str) -> Process | None:
        index = self._read_index()
        target_id = index["by_name"].get(process_name)
        if not isinstance(target_id, str):
            return None
        return self.get(target_id)

    def list(self) -> Sequence[Process]:
        index = self._read_index()
        processes: list[Process] = []
        for process_id in index["process_ids"]:
            process = self.get(process_id)
            if process is not None:
                processes.append(process)
        return processes

    def upsert(self, process: Process) -> None:
        payload = process.to_dict()
        payload["schema_version"] = PROCESS_SCHEMA_VERSION
        atomic_write_json(self._process_path(process.process_id), payload)
        index = self._read_index()
        if process.process_id not in index["process_ids"]:
            index["process_ids"].append(process.process_id)
        self._refresh_name_mapping(index, process)
        index["updated_at"] = now_str()
        atomic_write_json(self.root / INDEX_FILE_NAME, index)

    def allocate_run(
        self,
        process_id: str,
        *,
        process_name: str | None = None,
        kind: ProcessKind = "oneshot",
        run_id: str | None = None,
    ) -> Process:
        lock_path = self._lock_path(process_id)
        with file_lock(lock_path):
            process = self.get(process_id)
            if process is None:
                if not process_name:
                    raise ValueError("process_name is required to create a process record")
                timestamp = self.now()
                process = Process(
                    process_id=process_id,
                    process_name=process_name,
                    kind=kind,
                    status="running",
                    created_at=timestamp,
                    last_seen_at=timestamp,
                    last_heartbeat_at=timestamp,
                    updated_at=timestamp,
                    active_run_id=run_id,
                    last_run_outcome=None,
                    run_index=0,
                    next_run_index=1,
                )
            timestamp = self.now()
            allocated = max(process.next_run_index, 1)
            updated = Process(
                process_id=process.process_id,
                process_name=process.process_name,
                kind=process.kind,
                status="running",
                created_at=process.created_at,
                last_seen_at=timestamp,
                last_heartbeat_at=timestamp,
                updated_at=timestamp,
                active_run_id=run_id,
                last_run_outcome=process.last_run_outcome,
                run_index=allocated,
                next_run_index=allocated + 1,
            )
            self.upsert(updated)
            return updated

    def heartbeat(self, process_id: str) -> Process:
        lock_path = self._lock_path(process_id)
        with file_lock(lock_path):
            process = self.get(process_id)
            if process is None:
                raise KeyError(f"unknown process_id: {process_id}")
            timestamp = self.now()
            updated = Process(
                process_id=process.process_id,
                process_name=process.process_name,
                kind=process.kind,
                status=process.status,
                created_at=process.created_at,
                last_seen_at=timestamp,
                last_heartbeat_at=timestamp,
                updated_at=timestamp,
                active_run_id=process.active_run_id,
                last_run_outcome=process.last_run_outcome,
                run_index=process.run_index,
                next_run_index=process.next_run_index,
            )
            self.upsert(updated)
            return updated

    def _read_index(self) -> dict[str, object]:
        path = self.root / INDEX_FILE_NAME
        payload = _parse_json(path)
        if not isinstance(payload, dict):
            return self._rebuild_index()
        process_ids = payload.get("process_ids")
        by_name = payload.get("by_name")
        normalized = self._empty_index()
        if isinstance(process_ids, list):
            normalized["process_ids"] = [str(item) for item in process_ids if isinstance(item, str)]
        if isinstance(by_name, dict):
            normalized["by_name"] = {
                str(name): str(process_id) for name, process_id in by_name.items() if isinstance(name, str)
            }
        updated_at = payload.get("updated_at")
        if isinstance(updated_at, str):
            normalized["updated_at"] = updated_at
        return normalized

    def _empty_index(self) -> dict[str, object]:
        return {
            "schema_version": INDEX_SCHEMA_VERSION,
            "updated_at": now_str(),
            "process_ids": [],
            "by_name": {},
        }

    def _rebuild_index(self) -> dict[str, object]:
        index = self._empty_index()
        process_files = sorted(
            path for path in self.root.glob("*.json") if path.name != INDEX_FILE_NAME
        )
        for path in process_files:
            payload = _parse_json(path)
            if not isinstance(payload, dict):
                continue
            try:
                process = Process.from_dict(payload)
            except ValueError:
                continue
            index["process_ids"].append(process.process_id)
            self._refresh_name_mapping(index, process)
        return index

    def _refresh_name_mapping(self, index: dict[str, object], process: Process) -> None:
        by_name = index.get("by_name")
        if not isinstance(by_name, dict):
            by_name = {}
        else:
            by_name = dict(by_name)
        for name, process_id in list(by_name.items()):
            if process_id == process.process_id and name != process.process_name:
                by_name.pop(name, None)
        by_name[process.process_name] = process.process_id
        index["by_name"] = by_name

    def _process_path(self, process_id: str) -> Path:
        return self.root / f"{process_id}.json"

    def _lock_path(self, process_id: str) -> Path:
        return self.root / f"{process_id}.lock"


@dataclass(slots=True)
class FileProcessRegistryFactory:
    """Create process registries rooted at a resolved layout."""

    __api_version__ = "process_registry_factory/1.0"

    def create(self, layout: object) -> ProcessRegistryPort:
        processes_dir = getattr(layout, "processes_dir", None)
        if not isinstance(processes_dir, Path):
            raise TypeError("layout must provide a processes_dir Path")
        return FileProcessRegistry(processes_dir)


def list_processes(layout: object) -> list[Process]:
    """Load processes across canonical and legacy roots (canonical wins)."""
    process_roots = getattr(layout, "process_roots", None)
    if not callable(process_roots):
        raise TypeError("layout must provide process_roots()")
    seen: dict[str, Process] = {}
    for root in process_roots():
        if not isinstance(root, Path):
            continue
        registry = FileProcessRegistry(root)
        for process in registry.list():
            if process.process_id not in seen:
                seen[process.process_id] = process
    return list(seen.values())
