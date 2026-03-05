from __future__ import annotations

import json
from pathlib import Path

from noesis.domain.faculties.intuition import IntuitionMode
from noesis.domain.state import PlanKind, PlanStep
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


def test_state_repository_loads_existing_state_without_resetting_actions(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-load"
    run_dir.mkdir()
    context = EpisodeContext(
        run_dir=run_dir,
        episode_id="ep-load",
        seed=7,
        task="resume task",
        tags={"env": "test"},
        adapter_label="adapter:tooling",
        started_at="2025-01-01T00:00:00Z",
    )
    initial_repo = RuntimeStateRepository(context=context)
    state = initial_repo.init(context)
    state.set_plan(
        steps=[PlanStep(id="step-1", kind=PlanKind.ACT, description="resume action")],
        rationale="checkpointed",
        source="planner.resume",
    )
    state.set_outcome(status="partial", summary="paused", metrics={"x": 1.0})
    state.record_action(
        kind="tool",
        tool="adapter:tooling",
        input_excerpt="first",
        result_status="ok",
    )
    initial_repo.persist(state)

    reloaded_repo = RuntimeStateRepository(context=context)
    loaded = reloaded_repo.init(context)

    assert loaded.plan.steps[0].description == "resume action"
    assert loaded.outcomes.status == "partial"
    assert len(loaded.outcomes.actions) == 1

    next_action = loaded.record_action(
        kind="tool",
        tool="adapter:tooling",
        input_excerpt="second",
        result_status="ok",
    )
    assert next_action.id == "act-2"


def test_state_repository_does_not_persist_empty_adapter_label(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-empty-adapter"
    run_dir.mkdir()
    context = EpisodeContext(
        run_dir=run_dir,
        episode_id="ep-empty-adapter",
        seed=0,
        task="task",
        tags={},
        adapter_label="",
        started_at="2025-01-01T00:00:00Z",
    )
    repo = RuntimeStateRepository(context=context)
    _ = repo.init(context)

    payload = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    episode = payload.get("episode", {})
    assert "using" not in episode


def test_state_repository_empty_context_adapter_does_not_override_persisted_using(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-adapter-rehydrate"
    run_dir.mkdir()
    context_initial = EpisodeContext(
        run_dir=run_dir,
        episode_id="ep-adapter-rehydrate",
        seed=0,
        task="task",
        tags={},
        adapter_label="GraphAlpha",
        started_at="2025-01-01T00:00:00Z",
    )
    RuntimeStateRepository(context=context_initial).init(context_initial)

    context_rehydrate = EpisodeContext(
        run_dir=run_dir,
        episode_id="ep-adapter-rehydrate",
        seed=0,
        task="task",
        tags={},
        adapter_label="",
        started_at="2025-01-01T00:00:00Z",
    )
    loaded = RuntimeStateRepository(context=context_rehydrate).init(context_rehydrate)
    assert loaded.adapter_label == "GraphAlpha"
