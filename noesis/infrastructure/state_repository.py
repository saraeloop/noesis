"""
Filesystem-backed state repository.

Handles creating and persisting `state.json` while keeping the domain layer
pure and side-effect free.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol, Sequence, TYPE_CHECKING
import itertools
import json

from noesis.runtime.serialization import atomic_write_json
from noesis.domain.artifacts.immutability import ArtifactWriteMode
from noesis.runtime.artifacts.immutability import default_artifact_guard
from noesis.runtime.normalization import normalize_using
from noesis.domain.faculties.intuition import IntuitionMode
from noesis.domain.process import ProcessKind
from noesis.domain.state import (
    ActionArtifact,
    ActionRecord,
    NoesisState,
    OutcomeStatus,
    PlanKind,
    PlanStep,
    Provenance,
    StepStatus,
    create_state,
)
from noesis.domain.verification import Assertion

if TYPE_CHECKING:
    from noesis.runtime.prompt_recorder import PromptRecorder


class StateRepository(Protocol):
    """Abstraction over state persistence."""

    def init(self, request: "EpisodeContext") -> NoesisState:
        ...

    def persist(self, state: NoesisState) -> None:
        ...


@dataclass(slots=True)
class EpisodeContext:
    run_dir: Path
    episode_id: str
    seed: int
    task: str
    tags: dict[str, object]
    adapter_label: str
    started_at: str
    process_id: str | None = None
    process_name: str | None = None
    process_kind: ProcessKind | None = None
    process_run_index: int | None = None
    workspace: Path | None = None
    verify: Sequence[Assertion] | None = None
    intuition_mode: IntuitionMode = IntuitionMode.ADVISORY
    prompt_provenance_enabled: bool = False
    prompt_provenance_mode: Literal["full", "hash_only", "redacted"] = "hash_only"
    prompt_recorder: "PromptRecorder | None" = None


@dataclass(slots=True)
class RuntimeStateRepository(StateRepository):
    """Concrete repository that writes to `state.json` in the run directory."""

    context: EpisodeContext
    _state_path: Path | None = None
    _state: NoesisState | None = None

    def init(self, request: EpisodeContext | None = None) -> NoesisState:
        ctx = request or self.context
        if self._state is not None and self._state_path is not None:
            return self._state
        path = ctx.run_dir / "state.json"
        if path.exists():
            state = _read_state(path=path, context=ctx)
        else:
            state = create_state(
                episode_id=ctx.episode_id,
                seed=ctx.seed,
                task=ctx.task,
                started_at=ctx.started_at,
                tags=ctx.tags,
                adapter_label=ctx.adapter_label,
                process_id=ctx.process_id,
                process_name=ctx.process_name,
                process_kind=ctx.process_kind,
                process_run_index=ctx.process_run_index,
                intuition_mode=ctx.intuition_mode,
            )
            _write_state(path, state)
        self._state = state
        self._state_path = path
        return state

    def persist(self, state: NoesisState) -> None:
        if self._state_path is None:
            raise RuntimeError("state repository not initialized")
        _write_state(self._state_path, state)


def _write_state(path: Path, state: NoesisState) -> None:
    default_artifact_guard().ensure_write_allowed(
        episode_dir=path.parent,
        artifact=path.name,
        mode=ArtifactWriteMode.OVERWRITE,
    )
    payload = state.to_dict()
    episode = payload.get("episode")
    if isinstance(episode, dict):
        raw_using = episode.get("using")
        normalized = normalize_using(raw_using if isinstance(raw_using, str) else None)
        if normalized:
            episode["using"] = normalized.display
        elif isinstance(raw_using, str) and not raw_using.strip():
            episode.pop("using", None)
    atomic_write_json(path, payload)


def _read_state(*, path: Path, context: EpisodeContext) -> NoesisState:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return _rehydrate_state(payload=payload, context=context)


def _rehydrate_state(*, payload: dict[str, object], context: EpisodeContext) -> NoesisState:
    episode_payload = payload.get("episode")
    episode = episode_payload if isinstance(episode_payload, dict) else {}
    goal_payload = payload.get("goal")
    goal = goal_payload if isinstance(goal_payload, dict) else {}
    process_payload = payload.get("process")
    process = process_payload if isinstance(process_payload, dict) else {}

    task = str(goal.get("task") or context.task)
    seed = int(episode.get("seed")) if isinstance(episode.get("seed"), int) else context.seed
    started_at = str(episode.get("started_at") or context.started_at)
    tags = episode.get("tags")
    state_tags = dict(tags) if isinstance(tags, dict) else dict(context.tags)
    context_adapter = context.adapter_label.strip() if isinstance(context.adapter_label, str) else ""
    persisted_using = episode.get("using")
    persisted_adapter = persisted_using.strip() if isinstance(persisted_using, str) else ""
    adapter_label = context_adapter or persisted_adapter
    intuition_mode = _parse_intuition_mode(episode.get("intuition_mode"), fallback=context.intuition_mode)

    process_id = str(process.get("id")) if isinstance(process.get("id"), str) else context.process_id
    process_name = str(process.get("name")) if isinstance(process.get("name"), str) else context.process_name
    process_kind = str(process.get("kind")) if isinstance(process.get("kind"), str) else context.process_kind
    process_run_index = process.get("run_index") if isinstance(process.get("run_index"), int) else context.process_run_index

    state = create_state(
        episode_id=context.episode_id or str(episode.get("id") or context.episode_id),
        seed=seed,
        task=task,
        started_at=started_at,
        tags=state_tags,
        adapter_label=adapter_label,
        process_id=process_id,
        process_name=process_name,
        process_kind=process_kind,
        process_run_index=process_run_index,
        intuition_mode=intuition_mode,
    )

    plan_payload = payload.get("plan")
    if isinstance(plan_payload, dict):
        raw_steps = plan_payload.get("steps")
        steps: list[PlanStep] = []
        if isinstance(raw_steps, list):
            for index, item in enumerate(raw_steps, start=1):
                if not isinstance(item, dict):
                    continue
                steps.append(_parse_plan_step(item, index=index))
        rationale = plan_payload.get("rationale")
        source = plan_payload.get("source")
        if steps:
            state.set_plan(
                steps=steps,
                rationale=str(rationale) if isinstance(rationale, str) else None,
                source=str(source) if isinstance(source, str) else None,
            )

    beliefs_payload = payload.get("beliefs")
    if isinstance(beliefs_payload, list):
        state.beliefs = [item for item in beliefs_payload if isinstance(item, dict)]

    memory_payload = payload.get("memory")
    if isinstance(memory_payload, dict):
        scratchpad = memory_payload.get("scratchpad")
        if isinstance(scratchpad, str):
            state.scratchpad = scratchpad

    outcomes_payload = payload.get("outcomes")
    if isinstance(outcomes_payload, dict):
        status = outcomes_payload.get("status")
        summary = outcomes_payload.get("summary")
        metrics = outcomes_payload.get("metrics")
        parsed_status = _parse_outcome_status(status)
        state.set_outcome(
            status=parsed_status,
            summary=str(summary) if isinstance(summary, str) else None,
            metrics=metrics if isinstance(metrics, dict) else {},
        )
        actions_payload = outcomes_payload.get("actions")
        if isinstance(actions_payload, list):
            actions: list[ActionRecord] = []
            for item in actions_payload:
                if not isinstance(item, dict):
                    continue
                parsed = _parse_action_record(item)
                if parsed is not None:
                    actions.append(parsed)
            state.actions = actions
            state._action_counter = itertools.count(len(actions) + 1)

    links_payload = payload.get("links")
    if isinstance(links_payload, dict):
        state.links = {str(key): str(value) for key, value in links_payload.items() if isinstance(key, str)}
    return state


def _parse_intuition_mode(raw: object, *, fallback: IntuitionMode) -> IntuitionMode:
    if isinstance(raw, IntuitionMode):
        return raw
    if isinstance(raw, str):
        try:
            return IntuitionMode(raw)
        except ValueError:
            return fallback
    return fallback


def _parse_plan_step(payload: dict[str, object], *, index: int) -> PlanStep:
    raw_kind = payload.get("kind")
    raw_status = payload.get("status")
    kind = PlanKind.DEFAULT
    status = StepStatus.PENDING
    if isinstance(raw_kind, str):
        try:
            kind = PlanKind(raw_kind)
        except ValueError:
            kind = PlanKind.DEFAULT
    if isinstance(raw_status, str):
        try:
            status = StepStatus(raw_status)
        except ValueError:
            status = StepStatus.PENDING
    step_id = payload.get("id")
    description = payload.get("description")
    return PlanStep(
        id=str(step_id) if isinstance(step_id, str) and step_id else f"step-{index}",
        kind=kind,
        description=str(description) if isinstance(description, str) else "",
        status=status,
    )


def _parse_outcome_status(raw: object) -> OutcomeStatus:
    if isinstance(raw, OutcomeStatus):
        return raw
    if isinstance(raw, str):
        try:
            return OutcomeStatus(raw)
        except ValueError:
            return OutcomeStatus.PENDING
    return OutcomeStatus.PENDING


def _parse_action_record(payload: dict[str, object]) -> ActionRecord | None:
    action_id = payload.get("id")
    kind = payload.get("kind")
    tool = payload.get("tool")
    input_excerpt = payload.get("input_excerpt")
    result_status = payload.get("result_status")
    if not all(isinstance(value, str) for value in (action_id, kind, tool, input_excerpt, result_status)):
        return None

    provenance = payload.get("provenance")
    provenance_value = None
    if isinstance(provenance, dict):
        source = provenance.get("source")
        if isinstance(source, str):
            evidence_ids = provenance.get("evidence_ids")
            evidence = [str(item) for item in evidence_ids] if isinstance(evidence_ids, list) else []
            provenance_value = Provenance(source=source, evidence_ids=evidence)

    artifacts: list[ActionArtifact] = []
    artifacts_payload = payload.get("result_artifacts")
    if isinstance(artifacts_payload, list):
        for item in artifacts_payload:
            if not isinstance(item, dict):
                continue
            artifact_type = item.get("type")
            uri = item.get("uri")
            if not isinstance(artifact_type, str) or not isinstance(uri, str):
                continue
            artifacts.append(
                ActionArtifact(
                    type=artifact_type,
                    uri=uri,
                    sha256=str(item.get("sha256")) if isinstance(item.get("sha256"), str) else None,
                )
            )

    step_id = payload.get("step_id")
    timestamp = payload.get("timestamp")
    resolved_timestamp = (
        str(timestamp)
        if isinstance(timestamp, str)
        else datetime.now(timezone.utc).isoformat()
    )
    return ActionRecord(
        id=action_id,
        kind=kind,
        tool=tool,
        input_excerpt=input_excerpt,
        result_status=result_status,
        timestamp=resolved_timestamp,
        step_id=str(step_id) if isinstance(step_id, str) else None,
        provenance=provenance_value,
        result_artifacts=artifacts,
    )
