"""Protocol describing BYO runner integrations for NoesisSession."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol

from noesis.context import RuntimeContext
from noesis.intuition import Intuition

__all__ = ["RunnerProtocol", "SessionRunRequest"]


@dataclass(slots=True, frozen=True)
class SessionRunRequest:
    """Normalized inputs passed to external runner implementations."""

    task: str
    seed: int
    intuition: bool | Intuition | None
    tags: Mapping[str, object]


class RunnerProtocol(Protocol):
    """
    Interface adapters must implement to plug custom runners into a session.
    """

    def run(self, request: SessionRunRequest, *, context: RuntimeContext) -> str:
        """Execute a task and return the episode identifier for the run."""
