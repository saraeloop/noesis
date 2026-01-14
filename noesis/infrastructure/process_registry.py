"""Filesystem-backed process registry."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
import json

from noesis.domain.process import PROCESS_SCHEMA_VERSION, Process
from noesis.interfaces.process import ProcessRegistryPort
from noesis.runtime.serialization import atomic_write_json

INDEX_SCHEMA_VERSION = "process_registry/1.0"
INDEX_FILE_NAME = "index.json"

__all__ = ["FileProcessRegistry"]


def _utc_now() -> datetime:
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
        index["updated_at"] = _utc_now().isoformat()
        atomic_write_json(self.root / INDEX_FILE_NAME, index)

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
            "updated_at": _utc_now().isoformat(),
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
