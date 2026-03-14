from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping
from uuid import UUID, uuid4

from noesis.domain.action_candidates import ActionCandidate
from noesis.domain.planner.interfaces import EventBus
from noesis.domain.planner.minimal import MinimalActuator, MinimalPlanner
from noesis.domain.state import (
    ActionRecord,
    CognitiveEvent,
    CognitiveMetrics,
    CognitiveVerb,
    LineageTracker,
    NoesisState,
)
from noesis.usecases.episode_runner import (
    EpisodeDependencies,
    EpisodeInstrumentation,
    EpisodeRequest,
    EpisodeRunner,
)


@dataclass(slots=True)
class _FakeContext:
    run_dir: Path
    episode_id: str
    seed: int
    task: str
    tags: dict[str, object]
    adapter_label: str
    workspace: Path | None = None
    verify: list[object] | None = None
    prompt_recorder: object | None = None


class _FakeStateRepository:
    def __init__(self, context: _FakeContext) -> None:
        self.context = context
        self.persist_calls = 0
        self.last_state: NoesisState | None = None

    def init(self, request: _FakeContext | None = None) -> NoesisState:
        context = request or self.context
        return NoesisState(
            episode_id=context.episode_id,
            seed=context.seed,
            task=context.task,
            started_at="2025-01-01T00:00:00+00:00",
            tags=dict(context.tags),
            adapter_label=context.adapter_label,
        )

    def persist(self, state: NoesisState) -> None:
        self.persist_calls += 1
        self.last_state = state


class _FakeClock:
    def start(self, label: object) -> object:
        return label

    def stop(self, token: object) -> CognitiveMetrics:
        _ = token
        now = datetime.now(timezone.utc)
        return CognitiveMetrics(started_at=now, completed_at=now, duration_ms=0.0)

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class _FakeEmitter:
    def __init__(self) -> None:
        self.events: list[CognitiveEvent] = []

    def emit(self, event: CognitiveEvent, agent_id: str = "system") -> None:
        _ = agent_id
        self.events.append(event)


class _FakeEventHistory:
    def read(self, run_dir: Path) -> list[Mapping[str, object]]:
        _ = run_dir
        return []


class _FakeEventBus(EventBus):
    def __init__(self) -> None:
        self.actions: list[ActionRecord] = []

    def emit_plan(self, *, steps, rationale: str, source: str, metrics=None, caused_by=None) -> CognitiveEvent:  # type: ignore[override]
        _ = rationale, source, metrics, caused_by
        return CognitiveEvent(
            episode_id="ep-port-fake",
            verb=CognitiveVerb.PLAN,
            payload={"steps": [step.id for step in steps]},
            event_id=uuid4(),
        )

    def emit_direction(self, *, directive, caused_by=None) -> UUID:  # type: ignore[override]
        _ = directive, caused_by
        return uuid4()

    def emit_direction_payload(  # type: ignore[override]
        self,
        *,
        payload: Mapping[str, object],
        agent_id: str,
        caused_by=None,
    ) -> UUID:
        _ = payload, agent_id, caused_by
        return uuid4()

    def emit_action_candidate(  # type: ignore[override]
        self,
        *,
        candidate: ActionCandidate,
        caused_by=None,
    ) -> UUID:
        _ = candidate, caused_by
        return uuid4()

    def emit_governance(self, *, result, caused_by=None) -> UUID:  # type: ignore[override]
        _ = result, caused_by
        return uuid4()

    def emit_action(self, action: ActionRecord, *, metrics=None, step_status=None, caused_by=None) -> None:
        _ = metrics, step_status, caused_by
        self.actions.append(action)

    def emit_reflect(self, *, success: bool, reasons: list[str], metrics=None, caused_by=None) -> None:
        _ = success, reasons, metrics, caused_by


def test_episode_runner_supports_fake_ports(tmp_path: Path) -> None:
    context = _FakeContext(
        run_dir=tmp_path / "episode",
        episode_id="ep-port-fake",
        seed=0,
        task="Port isolation run",
        tags={},
        adapter_label="adapter:core.minimal",
    )
    deps = EpisodeDependencies(
        planner=MinimalPlanner(),
        actuator=MinimalActuator(tool_label="adapter:core.minimal"),
        event_bus=_FakeEventBus(),
        state_repository=_FakeStateRepository(context),
    )
    instrumentation = EpisodeInstrumentation(
        clock=_FakeClock(),
        emitter=_FakeEmitter(),
        lineage=LineageTracker(),
        event_history=_FakeEventHistory(),
        hooks=(),
    )
    runner = EpisodeRunner(deps, instrumentation=instrumentation)

    result = runner.run(EpisodeRequest(goal=context.task, beliefs=(), context=context))

    assert result.outcome.status == "ok"
    assert result.outcome.success is True
    assert deps.state_repository.persist_calls >= 1


def test_episode_runner_null_and_explicit_instrumentation_agree(tmp_path: Path) -> None:
    context = _FakeContext(
        run_dir=tmp_path / "episode-null",
        episode_id="ep-port-null",
        seed=0,
        task="Compare fallback modes",
        tags={},
        adapter_label="adapter:core.minimal",
    )
    deps_a = EpisodeDependencies(
        planner=MinimalPlanner(),
        actuator=MinimalActuator(tool_label="adapter:core.minimal"),
        event_bus=_FakeEventBus(),
        state_repository=_FakeStateRepository(context),
    )
    deps_b = EpisodeDependencies(
        planner=MinimalPlanner(),
        actuator=MinimalActuator(tool_label="adapter:core.minimal"),
        event_bus=_FakeEventBus(),
        state_repository=_FakeStateRepository(context),
    )
    request = EpisodeRequest(goal=context.task, beliefs=(), context=context)

    # No instrumentation passed: runner uses explicit null fallback.
    result_null = EpisodeRunner(deps_a).run(request)
    # Explicit instrumentation passed.
    result_explicit = EpisodeRunner(
        deps_b,
        instrumentation=EpisodeInstrumentation(
            clock=_FakeClock(),
            emitter=_FakeEmitter(),
            lineage=LineageTracker(),
            event_history=_FakeEventHistory(),
            hooks=(),
        ),
    ).run(request)

    assert result_null.outcome.status == result_explicit.outcome.status == "ok"
    assert result_null.outcome.success == result_explicit.outcome.success is True
    assert result_null.adapter_result == result_explicit.adapter_result == "success"
