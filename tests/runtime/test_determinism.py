from datetime import datetime, timedelta, timezone
from uuid import UUID

from noesis.runtime.determinism import DeterministicClock, DeterministicRNG


def test_deterministic_clock_advances_fixed_steps() -> None:
    clock = DeterministicClock(start_at=datetime(2030, 1, 1, tzinfo=timezone.utc), tick_ms=5.0)
    token = clock.start("observe")
    metrics = clock.stop(token)
    assert metrics.duration_ms == 5.0
    assert metrics.started_at == datetime(2030, 1, 1, tzinfo=timezone.utc)
    assert metrics.completed_at == datetime(2030, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=5)


def test_deterministic_rng_seeds_stdlib_and_bytes() -> None:
    rng = DeterministicRNG(seed=42)
    rng.reseed()
    first = rng.bytes(8)
    rng.reseed()
    second = rng.bytes(8)
    assert first == second


def test_deterministic_rng_uuid_namespace() -> None:
    rng = DeterministicRNG(seed=7)
    ns = UUID("00000000-0000-0000-0000-000000000001")
    # uuid5 is deterministic given namespace+name; seed does not alter uuid5 output.
    assert rng.uuid_namespace(ns, "rule") == UUID("83e12049-6bb1-5b51-a8cb-0fd0f1beade5")
