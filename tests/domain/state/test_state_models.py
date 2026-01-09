from __future__ import annotations

from noesis.domain.faculties.intuition import IntuitionMode
from noesis.domain.state import create_state


def test_create_state_sets_default_intuition_mode() -> None:
    state = create_state(
        episode_id="ep-1",
        seed=0,
        task="task",
        started_at="2025-01-01T00:00:00Z",
        tags={},
        adapter_label="adapter:tooling",
    )

    assert state.intuition_mode is IntuitionMode.ADVISORY


def test_create_state_accepts_intuition_mode() -> None:
    state = create_state(
        episode_id="ep-2",
        seed=1,
        task="task",
        started_at="2025-01-02T00:00:00Z",
        tags={},
        adapter_label="adapter:tooling",
        intuition_mode=IntuitionMode.INTERVENTIVE,
    )

    assert state.intuition_mode is IntuitionMode.INTERVENTIVE
