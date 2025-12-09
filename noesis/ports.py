"""
Public ports module.

Canonical import path:
    from noesis.ports import StateRepositoryPort, EventSinkPort, PromptRecorderPort, ...

Internally, this re-exports the Clean Architecture ports used by the use-case layer.
"""

from .usecases.ports import (  # type: ignore[F401]
    ClockPort,
    EpisodeInstrumentationPorts,
    EventHistoryPort,
    EventIdFactoryPort,
    EventSinkPort,
    PromptRecorderPort,
    StateRepositoryPort,
)

__all__ = [
    "StateRepositoryPort",
    "EventSinkPort",
    "EventHistoryPort",
    "PromptRecorderPort",
    "ClockPort",
    "EventIdFactoryPort",
    "EpisodeInstrumentationPorts",
]
