"""
Filesystem-backed state repository.

Handles creating and persisting `state.json` while keeping the domain layer
pure and side-effect free.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, TYPE_CHECKING

from noesis.runtime.serialization import atomic_write_json
from noesis.domain.state import NoesisState, create_state

if TYPE_CHECKING:
    from noesis.runtime.prompt_recorder import PromptRecorder


class StateRepository(Protocol):
    """Abstraction over state persistence."""

    def init(self, request: "EpisodeContext") -> NoesisState:
        ...

    def persist(self, state: NoesisState) -> None:
        ...


@dataclass(slots=True)
class EpisodeContext:
    run_dir: Path
    episode_id: str
    seed: int
    task: str
    tags: dict[str, object]
    adapter_label: str
    started_at: str
    prompt_provenance_enabled: bool = False
    prompt_provenance_mode: Literal["full", "hash_only"] = "hash_only"
    prompt_recorder: "PromptRecorder | None" = None


@dataclass(slots=True)
class RuntimeStateRepository(StateRepository):
    """Concrete repository that writes to `state.json` in the run directory."""

    context: EpisodeContext
    _state_path: Path | None = None
    _state: NoesisState | None = None

    def init(self, request: EpisodeContext | None = None) -> NoesisState:
        ctx = request or self.context
        if self._state is not None and self._state_path is not None:
            return self._state
        path = ctx.run_dir / "state.json"
        state = create_state(
            episode_id=ctx.episode_id,
            seed=ctx.seed,
            task=ctx.task,
            started_at=ctx.started_at,
            tags=ctx.tags,
            adapter_label=ctx.adapter_label,
        )
        _write_state(path, state)
        self._state = state
        self._state_path = path
        return state

    def persist(self, state: NoesisState) -> None:
        if self._state_path is None:
            raise RuntimeError("state repository not initialized")
        _write_state(self._state_path, state)


def _write_state(path: Path, state: NoesisState) -> None:
    payload = state.to_dict()
    atomic_write_json(path, payload)
