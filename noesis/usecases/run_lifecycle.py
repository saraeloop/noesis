"""Use cases for run interrupt/checkpoint/resume lifecycle operations."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, cast
from uuid import UUID, uuid4
import json

from noesis.context import RuntimeContext, get_config_snapshot
from noesis.domain.artifacts.immutability import ArtifactWriteMode
from noesis.domain.run_lifecycle import (
    CHECKPOINT_SCHEMA_VERSION,
    CheckpointConsistencyError,
    CheckpointNotFoundError,
    MissingCausalParentError,
    RunCheckpoint,
    RunLifecycleState,
    RunSealedError,
    assert_valid_transition,
)
from noesis.infrastructure.immutability import FinalizationSealStatus
from noesis.runtime.artifacts.immutability import default_artifact_guard
from noesis.runtime.artifacts.manifest import compute_sha256
from noesis.runtime.events import runtime_lifecycle_event
from noesis.runtime.paths import NoesisPaths, find_episode_dir, resolve_noesis_paths
from noesis.runtime.serialization import atomic_write_json, canonical_dumps
from noesis.runtime.utils import now
from noesis.trace.events import read_events

CHECKPOINTS_DIR = "checkpoints"
CHECKPOINT_FILE = "checkpoint.json"

__all__ = [
    "RunLifecycleService",
    "create_run_lifecycle_service",
]


@dataclass(slots=True)
class RunLifecycleService:
    """Manage interrupt/checkpoint/resume evidence for a run."""

    layout: NoesisPaths
    now_fn: Callable[[], str] = now
    id_factory: Callable[[], UUID] = uuid4

    def interrupt(
        self,
        run_id: str,
        *,
        reason: str | None = None,
        caused_by: str | None = None,
    ) -> str:
        run_dir = self._resolve_run_dir(run_id)
        self._ensure_unsealed(run_dir=run_dir, run_id=run_id)
        self._assert_transition(run_dir=run_dir, to_state="interrupted")
        parent_id = caused_by or self._last_event_id(run_dir=run_dir)
        payload: dict[str, Any] = {
            "kind": "run.interrupt",
            "status": "interrupted",
        }
        if reason:
            payload["reason"] = reason
        event_id = runtime_lifecycle_event(
            run_dir,
            run_id,
            event_type="run.interrupt",
            payload=payload,
            caused_by=parent_id,
            now_fn=self.now_fn,
            id_factory=self.id_factory,
        )
        return str(event_id)

    def checkpoint(
        self,
        run_id: str,
        *,
        caused_by: str | None = None,
    ) -> RunCheckpoint:
        run_dir = self._resolve_run_dir(run_id)
        self._ensure_unsealed(run_dir=run_dir, run_id=run_id)
        self._assert_transition(run_dir=run_dir, to_state="paused")

        events = read_events(run_dir)
        last_event_id = caused_by or self._extract_event_id(events[-1] if events else None)
        if not last_event_id:
            raise MissingCausalParentError("checkpoint requires a causal parent event id")

        checkpoint_id = f"chk_{self.id_factory().hex[:12]}"
        checkpoint = RunCheckpoint(
            schema_version=CHECKPOINT_SCHEMA_VERSION,
            run_id=run_id,
            checkpoint_id=checkpoint_id,
            created_at=self.now_fn(),
            event_offset=len(events),
            last_event_id=last_event_id,
            state_hash=self._required_state_hash(run_dir),
            artifact_manifest_hash=self._artifact_digest(run_dir),
            adapter_label=self._state_adapter_label(run_dir),
        )

        relative = Path(CHECKPOINTS_DIR) / checkpoint_id / CHECKPOINT_FILE
        self._write_checkpoint(run_dir=run_dir, relative_path=relative, checkpoint=checkpoint)

        runtime_lifecycle_event(
            run_dir,
            run_id,
            event_type="run.checkpoint",
            payload={
                "kind": "run.checkpoint",
                "status": "paused",
                "checkpoint_id": checkpoint_id,
                "event_offset": checkpoint.event_offset,
                "checkpoint_path": relative.as_posix(),
            },
            caused_by=last_event_id,
            now_fn=self.now_fn,
            id_factory=self.id_factory,
        )
        return checkpoint

    def load_checkpoint_for_resume(
        self,
        run_id: str,
        *,
        checkpoint_id: str,
    ) -> RunCheckpoint:
        """Load and validate a checkpoint for continuation orchestration."""
        run_dir = self._resolve_run_dir(run_id)
        self._ensure_unsealed(run_dir=run_dir, run_id=run_id)
        checkpoint = self._load_checkpoint(run_dir=run_dir, checkpoint_id=checkpoint_id)
        self._assert_checkpoint_consistency(run_dir=run_dir, checkpoint=checkpoint)
        return checkpoint

    def resume(
        self,
        run_id: str,
        *,
        checkpoint_id: str,
        caused_by: str | None = None,
    ) -> str:
        run_dir = self._resolve_run_dir(run_id)
        self._ensure_unsealed(run_dir=run_dir, run_id=run_id)
        self._assert_transition(run_dir=run_dir, to_state="resuming")

        checkpoint = self._load_checkpoint(run_dir=run_dir, checkpoint_id=checkpoint_id)
        self._assert_checkpoint_consistency(run_dir=run_dir, checkpoint=checkpoint)

        latest_event_id = self._last_event_id(run_dir=run_dir)
        if caused_by is not None and caused_by not in {checkpoint.last_event_id, latest_event_id}:
            raise CheckpointConsistencyError(
                "resume caused_by must match checkpoint last_event_id or the latest run event id"
            )
        parent_id = caused_by or latest_event_id
        event_id = runtime_lifecycle_event(
            run_dir,
            run_id,
            event_type="run.resume",
            payload={
                "kind": "run.resume",
                "status": "resuming",
                "checkpoint_id": checkpoint_id,
                "event_offset": checkpoint.event_offset,
                "resume_strategy": "same_run_id",
            },
            caused_by=parent_id,
            now_fn=self.now_fn,
            id_factory=self.id_factory,
        )
        return str(event_id)

    def _resolve_run_dir(self, run_id: str) -> Path:
        found = find_episode_dir(run_id, self.layout)
        if found is not None:
            return found
        candidate = self.layout.episodes_dir / run_id
        if not candidate.exists():
            raise FileNotFoundError(f"run '{run_id}' was not found")
        return candidate

    def resolve_run_dir(self, run_id: str) -> Path:
        """Resolve run directory for callers that orchestrate continuation flows."""
        return self._resolve_run_dir(run_id)

    def _ensure_unsealed(self, *, run_dir: Path, run_id: str) -> None:
        if FinalizationSealStatus().is_sealed(run_dir):
            raise RunSealedError(f"run '{run_id}' is sealed and cannot accept lifecycle mutations")

    def _required_state_hash(self, run_dir: Path) -> str:
        state_path = run_dir / "state.json"
        if not state_path.exists():
            raise CheckpointConsistencyError("checkpoint requires state.json to exist")
        return compute_sha256(state_path)

    def _state_adapter_label(self, run_dir: Path) -> str | None:
        state_path = run_dir / "state.json"
        if not state_path.exists():
            return None
        try:
            payload = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(payload, dict):
            return None
        episode = payload.get("episode")
        if not isinstance(episode, dict):
            return None
        using = episode.get("using")
        if isinstance(using, str) and using.strip():
            return using
        return None

    def _artifact_digest(self, run_dir: Path) -> str:
        manifest_path = run_dir / "manifest.json"
        if manifest_path.exists():
            return compute_sha256(manifest_path)

        artifact_names = [
            "events.jsonl",
            "prompts.jsonl",
            "state.json",
            "summary.json",
            "learn.jsonl",
        ]
        files: list[dict[str, object]] = []
        for name in artifact_names:
            path = run_dir / name
            if not path.exists() or not path.is_file():
                continue
            files.append(
                {
                    "name": name,
                    "sha256": compute_sha256(path),
                    "size_bytes": path.stat().st_size,
                }
            )
        payload = {
            "schema_version": "checkpoint_artifact_digest/1.0.0",
            "files": files,
        }
        digest = sha256(canonical_dumps(payload).encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def _write_checkpoint(self, *, run_dir: Path, relative_path: Path, checkpoint: RunCheckpoint) -> None:
        artifact = relative_path.as_posix()
        default_artifact_guard().ensure_write_allowed(
            episode_dir=run_dir,
            artifact=artifact,
            mode=ArtifactWriteMode.OVERWRITE,
        )
        atomic_write_json(run_dir / relative_path, checkpoint.to_dict())

    def _load_checkpoint(self, *, run_dir: Path, checkpoint_id: str) -> RunCheckpoint:
        path = run_dir / CHECKPOINTS_DIR / checkpoint_id / CHECKPOINT_FILE
        if not path.exists():
            raise CheckpointNotFoundError(f"checkpoint '{checkpoint_id}' not found")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as err:
            raise CheckpointConsistencyError(f"checkpoint '{checkpoint_id}' payload is invalid JSON") from err
        if not isinstance(payload, dict):
            raise CheckpointConsistencyError(f"checkpoint '{checkpoint_id}' payload must be an object")
        checkpoint = RunCheckpoint.from_dict(payload)
        if checkpoint.checkpoint_id != checkpoint_id:
            raise CheckpointConsistencyError(
                f"checkpoint id mismatch: expected '{checkpoint_id}', got '{checkpoint.checkpoint_id}'"
            )
        return checkpoint

    def _assert_checkpoint_consistency(self, *, run_dir: Path, checkpoint: RunCheckpoint) -> None:
        events = read_events(run_dir)
        if len(events) < checkpoint.event_offset:
            raise CheckpointConsistencyError("checkpoint event_offset exceeds current event history")
        event = events[checkpoint.event_offset - 1]
        event_id = self._extract_event_id(event)
        if event_id != checkpoint.last_event_id:
            raise CheckpointConsistencyError(
                "checkpoint causal anchor does not match current event history"
            )
        current_state_hash = self._required_state_hash(run_dir)
        if current_state_hash != checkpoint.state_hash:
            raise CheckpointConsistencyError(
                "checkpoint state hash does not match current state.json"
            )

    def _assert_transition(self, *, run_dir: Path, to_state: RunLifecycleState) -> None:
        from_state = self._current_lifecycle_state(run_dir=run_dir)
        assert_valid_transition(from_state, to_state)

    def _current_lifecycle_state(self, *, run_dir: Path) -> RunLifecycleState:
        state: RunLifecycleState = "running"
        for event in read_events(run_dir):
            if event.get("phase") != "runtime":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            status = payload.get("status")
            if isinstance(status, str):
                normalized = status.strip().lower()
                if normalized in {"running", "interrupted", "paused", "resuming", "success", "failed", "vetoed", "cancelled", "error"}:
                    state = cast(RunLifecycleState, normalized)
        return state

    def _last_event_id(self, *, run_dir: Path) -> str:
        events = read_events(run_dir)
        event_id = self._extract_event_id(events[-1] if events else None)
        if not event_id:
            raise MissingCausalParentError("run has no causal parent event")
        return event_id

    @staticmethod
    def _extract_event_id(event: dict[str, object] | None) -> str | None:
        if not isinstance(event, dict):
            return None
        event_id = event.get("id")
        if isinstance(event_id, str) and event_id.strip():
            return event_id
        return None


def create_run_lifecycle_service(
    *,
    context: RuntimeContext | None,
    workspace: Path | None,
) -> RunLifecycleService:
    """Build a run lifecycle service from runtime configuration."""
    if context is None:
        snapshot = get_config_snapshot()
    else:
        config_port = context.require("config", getattr(context.config_port, "__api_version__", "config/1.0-rc1"))
        snapshot = config_port.get()
    layout = resolve_noesis_paths(workspace=workspace, runs_dir=snapshot.runs_dir)
    return RunLifecycleService(layout=layout)
