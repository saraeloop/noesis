"""
Ports for episode orchestration (Clean Architecture boundary).

These abstractions allow the use-case layer to remain decoupled from
filesystem-bound implementations. Infrastructure adapters must satisfy
these protocols; structural typing keeps existing runtime classes compatible.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence
from uuid import UUID

from noesis.domain.state import CognitiveEvent, NoesisState


class StateRepositoryPort(Protocol):
    """State persistence boundary."""

    context: Any

    def init(self, request: Any | None = None) -> NoesisState:
        ...

    def persist(self, state: NoesisState) -> None:
        ...


class EventSinkPort(Protocol):
    """Event emission boundary."""

    def emit(self, event: CognitiveEvent, agent_id: str = "system") -> None:
        ...


class EventHistoryPort(Protocol):
    """Historical event access (used to seed lineage)."""

    def read(self, run_dir: Path) -> Sequence[Mapping[str, Any]]:
        ...


class PromptRecorderPort(Protocol):
    """Prompt provenance boundary."""

    def is_enabled(self) -> bool:
        ...

    def record(
        self,
        *,
        phase: str,
        agent_id: str,
        rendered: str,
        role: str | None = None,
        kind: str | None = None,
        model: str | None = None,
        template_id: str | None = None,
        template: str | None = None,
        variables: Mapping[str, object] | None = None,
        tags: Mapping[str, str] | None = None,
        event_id: str | None = None,
        outcome_event_id: str | None = None,
        timestamp: str | None = None,
        now: Any | None = None,
    ) -> None:
        ...


class EpisodeContextPort(Protocol):
    """Episode execution context exposed to use-case orchestration."""

    run_dir: Path
    episode_id: str
    seed: int
    task: str
    tags: Mapping[str, object]
    adapter_label: str
    workspace: Path | None
    verify: Sequence[Any] | None
    prompt_recorder: PromptRecorderPort | None


class ClockPort(Protocol):
    """Clock used for phase timing."""

    def start(self, label: Any) -> Any:
        ...

    def stop(self, token: Any) -> Any:
        ...

    def now(self) -> datetime:
        ...


class EventIdFactoryPort(Protocol):
    """Factory for deterministic event IDs."""

    def __call__(self) -> UUID:
        ...


@dataclass(slots=True)
class EpisodeInstrumentationPorts:
    clock: ClockPort
    emitter: EventSinkPort
    event_history: EventHistoryPort
    prompt_recorder: PromptRecorderPort | None
    now: Any
    event_id_factory: EventIdFactoryPort
    hooks: Any
    lineage: Any
