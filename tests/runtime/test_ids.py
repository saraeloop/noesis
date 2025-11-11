from __future__ import annotations

from noesis.runtime.artifacts.ids import new_episode_ulid


def test_ulids_are_monotonic() -> None:
    ids = [new_episode_ulid(seed=i) for i in range(10_000)]
    assert ids == sorted(ids)
