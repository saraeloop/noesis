"""Runtime helpers for resolving the Noēsis on-disk layout."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

__all__ = [
    "NoesisPaths",
    "resolve_noesis_paths",
    "resolve_noesis_root",
    "legacy_episode_roots",
    "legacy_process_roots",
    "find_episode_dir",
]


@dataclass(frozen=True, slots=True)
class NoesisPaths:
    """Resolved Noēsis filesystem layout."""

    root: Path
    episodes_dir: Path
    processes_dir: Path
    legacy_episode_dirs: tuple[Path, ...] = ()
    legacy_process_dirs: tuple[Path, ...] = ()

    def episode_roots(self) -> tuple[Path, ...]:
        return (self.episodes_dir,) + self.legacy_episode_dirs

    def process_roots(self) -> tuple[Path, ...]:
        return (self.processes_dir,) + self.legacy_process_dirs


def resolve_noesis_paths(*, workspace: Path | None, runs_dir: Path) -> NoesisPaths:
    base = _default_workspace(workspace, runs_dir)
    root = resolve_noesis_root(workspace=base, runs_dir=runs_dir)
    episodes_dir = root / "episodes"
    processes_dir = root / "processes"
    legacy_episodes = legacy_episode_roots(workspace=base, runs_dir=runs_dir, root=root, episodes_dir=episodes_dir)
    legacy_processes = legacy_process_roots(
        workspace=base,
        runs_dir=runs_dir,
        root=root,
        processes_dir=processes_dir,
    )
    return NoesisPaths(
        root=root,
        episodes_dir=episodes_dir,
        processes_dir=processes_dir,
        legacy_episode_dirs=tuple(legacy_episodes),
        legacy_process_dirs=tuple(legacy_processes),
    )


def resolve_noesis_root(*, workspace: Path, runs_dir: Path) -> Path:
    workspace = workspace.expanduser().resolve()
    runs_dir = runs_dir.expanduser().resolve()
    if runs_dir.name == ".noesis":
        return runs_dir
    candidate = runs_dir / ".noesis"
    if candidate.exists():
        return candidate
    if runs_dir.exists() and (runs_dir / "episodes").exists():
        return runs_dir
    return workspace / ".noesis"


def legacy_episode_roots(
    *,
    workspace: Path,
    runs_dir: Path,
    root: Path,
    episodes_dir: Path,
) -> tuple[Path, ...]:
    candidates = [
        runs_dir.expanduser().resolve(),
        runs_dir.expanduser().resolve() / "runs",
        workspace.expanduser().resolve() / "runs",
        root / "runs",
        root.parent / ".noesis" / "runs",
    ]
    return _dedupe_paths(path for path in candidates if _is_legacy_root(path, root, episodes_dir))


def legacy_process_roots(
    *,
    workspace: Path,
    runs_dir: Path,
    root: Path,
    processes_dir: Path,
) -> tuple[Path, ...]:
    candidates = [
        runs_dir.expanduser().resolve() / "processes",
        runs_dir.expanduser().resolve() / "runs" / "processes",
        workspace.expanduser().resolve() / "runs" / "processes",
        root / "runs" / "processes",
    ]
    return _dedupe_paths(path for path in candidates if _is_legacy_root(path, root, processes_dir))


def find_episode_dir(episode_id: str, paths: NoesisPaths) -> Path | None:
    for root in paths.episode_roots():
        candidate = root / episode_id
        if candidate.exists():
            return candidate
    return None


def _is_legacy_root(path: Path, root: Path, canonical: Path) -> bool:
    if path == root or path == canonical:
        return False
    return path.exists()


def _dedupe_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        result.append(path)
    return tuple(result)


def _default_workspace(workspace: Path | None, runs_dir: Path) -> Path:
    if workspace is not None:
        return workspace.expanduser().resolve()
    runs_dir = runs_dir.expanduser()
    if runs_dir.is_absolute():
        return runs_dir.parent.resolve()
    return Path.cwd().resolve()
