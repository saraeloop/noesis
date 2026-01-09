from __future__ import annotations

from pathlib import Path

from noesis.domain.faculties.intuition import IntuitionMode
from noesis.infrastructure.state_repository import EpisodeContext, RuntimeStateRepository


def test_state_repository_passes_intuition_mode(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    context = EpisodeContext(
        run_dir=run_dir,
        episode_id="ep-1",
        seed=0,
        task="task",
        tags={},
        adapter_label="adapter:tooling",
        started_at="2025-01-01T00:00:00Z",
        intuition_mode=IntuitionMode.HYBRID,
    )
    repo = RuntimeStateRepository(context=context)

    state = repo.init(context)

    assert state.intuition_mode is IntuitionMode.HYBRID
