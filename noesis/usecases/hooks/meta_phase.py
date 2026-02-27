"""
Meta-phase hooks allow governance or observability logic to run around each
cognitive verb without polluting the EpisodeRunner orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from noesis.domain.state.cognitive import CognitiveEvent, CognitiveVerb
from noesis.usecases.ports import EpisodeContextPort

__all__ = ["MetaPhaseHook", "CompositeMetaPhaseHook", "NullMetaPhaseHook"]


class MetaPhaseHook(Protocol):
    """Hook contract executed before and after each cognitive verb."""

    def before_phase(self, verb: CognitiveVerb, context: EpisodeContextPort) -> None:
        ...

    def after_phase(
        self,
        verb: CognitiveVerb,
        context: EpisodeContextPort,
        event: CognitiveEvent,
    ) -> None:
        ...


@dataclass(slots=True)
class CompositeMetaPhaseHook:
    """Executes a sequence of hooks in order."""

    hooks: Sequence[MetaPhaseHook]

    def before_phase(self, verb: CognitiveVerb, context: EpisodeContextPort) -> None:
        for hook in self.hooks:
            hook.before_phase(verb, context)

    def after_phase(self, verb: CognitiveVerb, context: EpisodeContextPort, event: CognitiveEvent) -> None:
        for hook in self.hooks:
            hook.after_phase(verb, context, event)


class NullMetaPhaseHook(MetaPhaseHook):
    """Convenience hook that performs no-ops."""

    def before_phase(self, verb: CognitiveVerb, context: EpisodeContextPort) -> None:  # noqa: D401
        return None

    def after_phase(self, verb: CognitiveVerb, context: EpisodeContextPort, event: CognitiveEvent) -> None:  # noqa: D401
        return None
