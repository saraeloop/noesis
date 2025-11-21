"""
Replay/compare helpers for deterministic runs.

These utilities mirror the normalization logic used by determinism tests to
decide whether two episode directories drift structurally or byte-for-byte.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Literal
import json


DriftStatus = Literal["NO_DRIFT", "DRIFT"]


@dataclass(slots=True)
class DriftMismatch:
    """Describes a specific drift between two runs."""

    artifact: str
    detail: str


@dataclass(slots=True)
class DriftResult:
    """Aggregate outcome of a run comparison."""

    status: DriftStatus
    mismatches: list[DriftMismatch]

    @property
    def is_drift(self) -> bool:
        return self.status == "DRIFT"


def compare_runs(dir_a: Path | str, dir_b: Path | str) -> DriftResult:
    """
    Compare two episode directories for drift.

    - summary.json must be byte-identical.
    - state.json and manifest.json are compared structurally after
      normalizing observational fields.
    - events.jsonl is compared structurally after removing timestamps/IDs/snapshots.
    - Both runs must contain the same file set.
    """
    run_a = Path(dir_a)
    run_b = Path(dir_b)
    mismatches: list[DriftMismatch] = []

    _assert_exists(run_a, mismatches)
    _assert_exists(run_b, mismatches)
    if mismatches:
        return DriftResult(status="DRIFT", mismatches=mismatches)

    _compare_file_sets(run_a, run_b, mismatches)
    _compare_bytes(run_a, run_b, "summary.json", mismatches)
    _compare_normalized(run_a, run_b, "state.json", _normalize_state, mismatches)
    _compare_normalized(run_a, run_b, "manifest.json", _normalize_manifest, mismatches)
    _compare_normalized_events(run_a, run_b, mismatches)

    status: DriftStatus = "DRIFT" if mismatches else "NO_DRIFT"
    return DriftResult(status=status, mismatches=mismatches)


def _assert_exists(path: Path, mismatches: list[DriftMismatch]) -> None:
    if not path.exists():
        mismatches.append(DriftMismatch(artifact=str(path), detail="missing run directory"))
    elif not path.is_dir():
        mismatches.append(DriftMismatch(artifact=str(path), detail="not a directory"))


def _compare_file_sets(dir_a: Path, dir_b: Path, mismatches: list[DriftMismatch]) -> None:
    files_a = sorted(p.name for p in dir_a.iterdir() if p.is_file())
    files_b = sorted(p.name for p in dir_b.iterdir() if p.is_file())
    if files_a != files_b:
        mismatches.append(
            DriftMismatch(
                artifact="files",
                detail=f"file sets differ: {files_a} vs {files_b}",
            )
        )


def _compare_bytes(dir_a: Path, dir_b: Path, name: str, mismatches: list[DriftMismatch]) -> None:
    path_a = dir_a / name
    path_b = dir_b / name
    if not path_a.exists() or not path_b.exists():
        mismatches.append(DriftMismatch(artifact=name, detail="missing file"))
        return
    if path_a.read_bytes() != path_b.read_bytes():
        mismatches.append(DriftMismatch(artifact=name, detail="bytes differ"))


def _compare_normalized(
    dir_a: Path,
    dir_b: Path,
    name: str,
    normalizer: Callable[[dict[str, Any]], dict[str, Any]],
    mismatches: list[DriftMismatch],
) -> None:
    path_a = dir_a / name
    path_b = dir_b / name
    if not path_a.exists() or not path_b.exists():
        mismatches.append(DriftMismatch(artifact=name, detail="missing file"))
        return
    data_a = normalizer(json.loads(path_a.read_text(encoding="utf-8")))
    data_b = normalizer(json.loads(path_b.read_text(encoding="utf-8")))
    if data_a != data_b:
        mismatches.append(DriftMismatch(artifact=name, detail="structural drift"))


def _compare_normalized_events(dir_a: Path, dir_b: Path, mismatches: list[DriftMismatch]) -> None:
    path_a = dir_a / "events.jsonl"
    path_b = dir_b / "events.jsonl"
    if not path_a.exists() or not path_b.exists():
        mismatches.append(DriftMismatch(artifact="events.jsonl", detail="missing file"))
        return
    events_a = [_normalize_event(json.loads(line)) for line in _iter_lines(path_a)]
    events_b = [_normalize_event(json.loads(line)) for line in _iter_lines(path_b)]
    if events_a != events_b:
        mismatches.append(DriftMismatch(artifact="events.jsonl", detail="structural drift"))


def _iter_lines(path: Path) -> Iterable[str]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield line


def _normalize_state(state: dict[str, Any]) -> dict[str, Any]:
    episode = state.get("episode")
    if isinstance(episode, dict):
        episode.pop("started_at", None)
    plan = state.get("plan")
    if isinstance(plan, dict):
        plan.pop("updated_at", None)
    outcomes = state.get("outcomes")
    if isinstance(outcomes, dict):
        actions = outcomes.get("actions")
        if isinstance(actions, list):
            for action in actions:
                if isinstance(action, dict):
                    action.pop("timestamp", None)
    return state


def _normalize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    manifest.pop("created_at", None)
    files = manifest.get("files")
    if isinstance(files, list):
        for entry in files:
            if isinstance(entry, dict):
                entry.pop("sha256", None)
    return manifest


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    event.pop("timestamp", None)
    event.pop("id", None)
    _strip_timestamps_recursive(event)
    payload = event.get("payload")
    if isinstance(payload, dict):
        payload.pop("snapshot", None)
        experimental = payload.get("experimental")
        if isinstance(experimental, dict):
            experimental.pop("snapshot", None)
    return event


def _strip_timestamps_recursive(obj: dict[str, Any]) -> None:
    timestamp_keys = {"timestamp", "started_at", "updated_at", "created_at", "completed_at"}
    for key in list(obj.keys()):
        if key in timestamp_keys:
            obj.pop(key, None)
            continue
        value = obj[key]
        if isinstance(value, dict):
            _strip_timestamps_recursive(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _strip_timestamps_recursive(item)
