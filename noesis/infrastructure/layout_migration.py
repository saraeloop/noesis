"""Migration helpers for legacy Noēsis layout roots."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import shutil

from noesis.runtime.paths import NoesisPaths
from noesis.runtime.serialization import atomic_write_json

__all__ = ["MigrationResult", "migrate_layout"]


@dataclass(slots=True)
class MigrationResult:
    episodes_copied: int = 0
    processes_copied: int = 0
    legacy_roots: tuple[str, ...] = ()
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "episodes_copied": self.episodes_copied,
            "processes_copied": self.processes_copied,
            "legacy_roots": list(self.legacy_roots),
            "warnings": list(self.warnings),
        }


def migrate_layout(layout: NoesisPaths) -> MigrationResult:
    layout.root.mkdir(parents=True, exist_ok=True)
    layout.episodes_dir.mkdir(parents=True, exist_ok=True)
    layout.processes_dir.mkdir(parents=True, exist_ok=True)
    result = MigrationResult(
        legacy_roots=tuple(str(path) for path in layout.legacy_episode_dirs + layout.legacy_process_dirs),
    )
    _copy_episodes(layout, result)
    _copy_processes(layout, result)
    _write_marker(layout, result)
    return result


def _copy_episodes(layout: NoesisPaths, result: MigrationResult) -> None:
    for root in layout.legacy_episode_dirs:
        if not root.exists():
            continue
        for entry in root.iterdir():
            if not entry.is_dir():
                continue
            if not entry.name.startswith("ep_"):
                continue
            target = layout.episodes_dir / entry.name
            if target.exists():
                continue
            try:
                shutil.copytree(entry, target)
                result.episodes_copied += 1
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"episode copy failed: {entry} -> {target} ({exc})")


def _copy_processes(layout: NoesisPaths, result: MigrationResult) -> None:
    for root in layout.legacy_process_dirs:
        if not root.exists():
            continue
        for entry in root.iterdir():
            if entry.is_dir() or entry.suffix != ".json":
                continue
            target = layout.processes_dir / entry.name
            if target.exists():
                continue
            try:
                shutil.copy2(entry, target)
                result.processes_copied += 1
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"process copy failed: {entry} -> {target} ({exc})")


def _write_marker(layout: NoesisPaths, result: MigrationResult) -> None:
    marker = {
        "migrated_at": datetime.now(timezone.utc).isoformat(),
        "legacy_roots": list(result.legacy_roots),
        "episodes_copied": result.episodes_copied,
        "processes_copied": result.processes_copied,
        "warnings": list(result.warnings),
    }
    atomic_write_json(layout.root / "MIGRATED_FROM.json", marker)
