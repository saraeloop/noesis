"""Protocol describing BYO runner integrations for NoesisSession."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol, Sequence

from noesis.context import RuntimeContext
from noesis.intuition import Intuition
from noesis.domain.verification import Assertion

__all__ = ["RunnerProtocol", "SessionRunRequest"]


@dataclass(slots=True, frozen=True)
class SessionRunRequest:
    """Normalized inputs passed to external runner implementations."""

    task: str
    seed: int
    intuition: bool | Intuition | None
    tags: Mapping[str, object]
    workspace: Path | None = None
    verify: Sequence[Assertion] | None = None


class RunnerProtocol(Protocol):
    """
    Interface adapters must implement to plug custom runners into a session.
    """

    def run(self, request: SessionRunRequest, *, context: RuntimeContext) -> str:
        """Execute a task and return the episode identifier for the run."""
