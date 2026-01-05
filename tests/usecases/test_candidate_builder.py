from __future__ import annotations

from pathlib import Path

from noesis.domain.state import NoesisState, PlanKind, PlanStep
from noesis.infrastructure.state_repository import EpisodeContext
from noesis.usecases.actuation.candidate_builder import DefaultActionCandidateBuilder
from noesis.usecases.episode_runner import EpisodeRequest


def test_candidate_builder_state_hash_is_stable_across_plan_timestamps() -> None:
    steps = [
        PlanStep(id="step-1", kind=PlanKind.ACT, description="Execute task"),
    ]
    state_a = NoesisState(
        episode_id="ep-1",
        seed=0,
        task="task",
        started_at="2025-01-01T00:00:00Z",
        tags={},
        adapter_label="adapter:tooling",
        plan_steps=list(steps),
        plan_updated_at="2025-01-01T00:00:00Z",
    )
    state_b = NoesisState(
        episode_id="ep-1",
        seed=0,
        task="task",
        started_at="2025-01-01T00:00:00Z",
        tags={},
        adapter_label="adapter:tooling",
        plan_steps=list(steps),
        plan_updated_at="2030-01-01T00:00:00Z",
    )
    context = EpisodeContext(
        run_dir=Path("."),
        episode_id="ep-1",
        seed=0,
        task="task",
        tags={},
        adapter_label="adapter:tooling",
        started_at="2025-01-01T00:00:00Z",
    )
    request = EpisodeRequest(goal="task", beliefs=(), context=context)
    builder = DefaultActionCandidateBuilder()

    candidate_a = builder.build(plan=steps, request=request, state=state_a)
    candidate_b = builder.build(plan=steps, request=request, state=state_b)

    assert candidate_a.state_hash == candidate_b.state_hash
