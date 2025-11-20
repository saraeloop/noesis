"""
Deterministic helpers for replayable runs and tests.

These utilities let the runtime operate with reproducible clocks and RNG sources
without polluting the domain layer:
- DeterministicClock: advances time in fixed increments for metrics.
- DeterministicRNG: seeds random/numpy and offers deterministic bytes/UUIDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterator, Optional
from uuid import UUID, uuid5
import os
import random

from noesis.domain.state.cognitive import CognitiveMetrics

__all__ = ["DeterministicClock", "DeterministicRNG"]


@dataclass(slots=True)
class DeterministicClock:
    """Fixed-step clock for deterministic phase metrics."""

    start_at: datetime = field(default_factory=lambda: datetime(2025, 1, 1, tzinfo=timezone.utc))
    tick_ms: float = 1.0
    _ticks: int = 0

    def start(self, _: object | None = None) -> int:
        token = self._ticks
        self._ticks += 1
        return token

    def stop(self, token: int) -> CognitiveMetrics:
        start = self.start_at + timedelta(milliseconds=token * self.tick_ms)
        end = start + timedelta(milliseconds=self.tick_ms)
        return CognitiveMetrics(
            started_at=start,
            completed_at=end,
            duration_ms=round(self.tick_ms, 3),
        )


@dataclass(slots=True)
class DeterministicRNG:
    """Reproducible RNG facade covering stdlib random, numpy (if present), and uuid-like values."""

    seed: int
    _rand: random.Random = field(init=False)

    def __post_init__(self) -> None:
        self._rand = random.Random(self.seed)

    def reseed(self, seed: Optional[int] = None) -> None:
        new_seed = self.seed if seed is None else seed
        self._rand.seed(new_seed)
        random.seed(new_seed)
        try:
            import numpy  # type: ignore

            numpy.random.seed(new_seed)  # pragma: no cover
        except ImportError:
            pass

    def bytes(self, length: int) -> bytes:
        return self._rand.randbytes(length)

    def uuid_namespace(self, namespace: UUID, name: str) -> UUID:
        return uuid5(namespace, name)

    def context(self) -> Iterator[None]:
        """Context manager to apply deterministic seeds."""
        class _Ctx:
            def __enter__(_self) -> None:
                self.reseed()

            def __exit__(_self, exc_type, exc, tb) -> None:
                # nothing to restore; deterministic seeding is idempotent
                return False

        return _Ctx()

    def patch_os_urandom(self) -> Callable[[], None]:
        """
        Monkey-patch os.urandom deterministically. Returns a restoration callable.
        Useful for ULID generation during golden runs.
        """
        original = os.urandom

        def _urandom(n: int) -> bytes:
            return self.bytes(n)

        os.urandom = _urandom  # type: ignore[assignment]

        def restore() -> None:
            os.urandom = original  # type: ignore[assignment]

        return restore
