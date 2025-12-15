"""
Execution core for Noēsis.

Responsibilities
    • Entry points: run(), solve(), run_using(), run_graph() (compat), set()
    • Orchestration: create episode IDs/dirs, emit start/observe/terminate events
    • Intuition: normalize policy/mode, record advisory events
    • Adapters: load graph, select adapter, execute, capture results/veto/errors
    • Summarization: read events → compute metrics → write summary.json with flags

Key invariants
    - Every episode yields a well-formed events.jsonl and summary.json (success, error, or veto).
    - Intuition is optional; when disabled, core behavior is still fully traceable.
    - Directional patches/vetoes are adapter-driven; core only standardizes flags/metrics.

Schema
    SCHEMA_VERSION declares the summary schema version baked into artifacts.

Architecture notes
    - _run_impl sets up determinism/context and then delegates to _run_minimal_episode or _run_adapter_episode.
    - Mode helpers own their orchestration and snapshot construction to keep responsibilities small.
    - _finalize_episode centralizes artifact writes (summary, manifest, index) shared by both paths.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, List, Final, Protocol, TYPE_CHECKING, Callable
from uuid import uuid4
from datetime import datetime, timezone

from .state import (
    PlanStep,
    PlanKind,
    StepStatus,
    OUTCOME_STATUS_OK,
    OUTCOME_STATUS_ERROR,
    OUTCOME_STATUS_VETOED,
    OUTCOME_STATUS_ABORTED,
    OUTCOME_STATUS_PARTIAL,
)
from .domain.state import LineageTracker
from .state.episode import begin_episode
from .episode import EpisodeIndex
# Domain / use-case layer imports
from .domain.planner.minimal import MinimalActuator, MinimalPlanner
from .domain.planner.meta import MetaPlanner
from .domain.faculties.governance import GovernanceFailurePolicy, GovernanceMode, PreActGovernor
from .infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from .interfaces.observability import RuntimeEventBus
from .interfaces.config import PlannerMode
from .trace.events import write_event, read_events
from .intuition import Intuition, IntuitionEvent, NullIntuition, IntuitionMode
from .exceptions import NoesisVeto
from .loader import load_graph, GraphSource
from .direction import DirectiveKind
from .runtime.events import direction_event
from copy import deepcopy
from .runtime.utils import now as _now
from .runtime.clock import RuntimeClock
from .runtime.events_emitter import CognitiveEventEmitter
from .runtime.prompt_recorder import PromptRecorder
from .runtime.events import (
    act_event as _act_event,
    ensure_act_event as _ensure_act_event,
    interpret_event as _interpret_event,
    observe_event as _observe_event,
    plan_event as _plan_event,
    reflect_event as _reflect_event,
    start_event as _start_event,
    terminate_event as _terminate_event,
)
from .runtime.summary import finalize_summary as _finalize_summary
from .trace.schema import SUMMARY_SCHEMA_VERSION
from .runtime.artifacts.ids import EpisodeIds
from .runtime.artifacts.writer import ManifestWriter
from .runtime.artifacts.manifest import MANIFEST_SCHEMA_VERSION, MANIFEST_FILE_NAME, compute_sha256
from .usecases.episode_runner import (
    EpisodeDependencies,
    EpisodeInstrumentation,
    EpisodeRequest,
    EpisodeRunner,
)
from .usecases.memory_sync import persist_episode_memory
from .context import RuntimeContext, get_context

if TYPE_CHECKING:
    from .runtime.session.models import DeterminismConfig

SCHEMA_VERSION: Final[str] = SUMMARY_SCHEMA_VERSION
EXCERPT_IN_LEN: Final[int] = 120
EXCERPT_OUT_LEN: Final[int] = 400
EPISODE_STORE_TTL_DAYS: Final[int] = 30


def _normalize_outcome_status(raw_status: str, *, success: bool) -> str:
    if raw_status == "ok":
        return OUTCOME_STATUS_OK
    if raw_status == "blocked":
        return OUTCOME_STATUS_VETOED
    if raw_status == "error":
        return OUTCOME_STATUS_ERROR
    if raw_status == "aborted":
        return OUTCOME_STATUS_ABORTED
    if raw_status == "partial":
        return OUTCOME_STATUS_PARTIAL
    return OUTCOME_STATUS_OK if success else OUTCOME_STATUS_ERROR


def _plan_steps_from_labels(labels: List[str]) -> List[PlanStep]:
    steps: List[PlanStep] = []
    for idx, label in enumerate(labels, start=1):
        steps.append(
            PlanStep(
                id=f"step-{idx}",
                kind=PlanKind.DEFAULT,
                description=label.strip(),
                status=StepStatus.PENDING,
            )
        )
    return steps


def _finalize_manifest(ctx: _EpCtx) -> tuple[Path, str]:
    writer = ManifestWriter(run_dir=ctx.run_dir, episode_id=ctx.episode_id)
    writer.finalize()
    digest = compute_sha256(writer.manifest_path)
    return writer.manifest_path, digest


def _normalize_intuition(
    intuition_mode: IntuitionMode, intuition: bool | Intuition | None
) -> tuple[Intuition, bool]:
    """Normalize intuition argument without mutating caller-supplied policies."""
    mode = intuition_mode

    if intuition is True:
        i = NullIntuition()
        i.mode = mode
        return i, True
    if intuition is False or intuition is None:
        i = NullIntuition()
        i.mode = mode
        return i, False
    # Caller supplied a concrete policy; keep its own .mode.
    assert hasattr(intuition, "advise"), "Intuition implementations must define advise()"
    return intuition, True


def _maybe_intuition(
    run_dir: Path,
    episode_id: str,
    enabled: bool,
    intuition: Intuition,
    snapshot: Dict[str, Any],
    *,
    now_fn: Callable[[], str] | None = None,
    id_factory: Callable[[], Any] | None = None,
) -> IntuitionEvent | None:
    if not enabled:
        return None
    evt: IntuitionEvent | None = intuition.advise(snapshot)
    if not evt:
        return None
    now_fn = now_fn or _now
    id_factory = id_factory or uuid4
    write_event(
        run_dir,
        {
            "id": str(id_factory()),
            "timestamp": now_fn(),
            "episode_id": episode_id,
            "agent_id": "intuition",
            "phase": "intuition",
            "payload": {
                "kind": evt.kind,
                "advice": evt.advice,
                "confidence": evt.confidence,
                "applied": evt.applied,
                "rationale": evt.rationale,
                "evidence_ids": evt.evidence_ids,
                # (mode is visible on policy; adapters may also echo it)
            },
            "evidence_ids": [],
        },
    )
    signals: List[str] = [f"directive:{evt.kind}", evt.advice]
    reasons = [evt.rationale] if evt.rationale else None
    _interpret_event(
        run_dir,
        episode_id,
        signals=signals,
        reasons=reasons,
        source="intuition",
        now_fn=now_fn,
        id_factory=id_factory,
    )

    plan_steps: List[str] = [f"{evt.kind}→{evt.target}"]
    if evt.patch:
        plan_steps.append(f"patch_keys:{','.join(sorted(evt.patch.keys()))}")
    _plan_event(
        run_dir,
        episode_id,
        steps=plan_steps,
        rationale=evt.rationale,
        source="intuition",
        now_fn=now_fn,
        id_factory=id_factory,
    )
    return evt


def _safe_using_label(using: GraphSource) -> str:
    if isinstance(using, str):
        return using
    target = getattr(using, "func", using)
    if callable(target):
        name = getattr(target, "__name__", None)
        if name:
            return name
    return target.__class__.__name__


def _load_graph(source: GraphSource) -> Any:
    return load_graph(source)


class _Adapter(Protocol):
    def execute(
        self,
        *,
        task: str,
        episode_id: str,
        run_dir: Path,
        intuition: Optional[Intuition] = None,
        seed: int = 0,
        tags: Optional[Dict[str, Any]] = None,
    ) -> Any:
        ...


def _select_adapter(graph_obj: Any, min_confidence: float) -> _Adapter:
    """
    Select a simple adapter for the given graph-like object.

    We intentionally avoid importing noesis.adapters.* here so that core/runtime
    stay decoupled from adapter implementations. Integration layers can wrap
    LangGraph/CrewAI/etc. explicitly.
    """

    class _CallableAdapter:
        def __init__(self, obj: Any, min_conf: float):
            self.obj = obj
            self._min_conf = min_conf
            # Check for input mapper attribute (like DictGraph has)
            self._input_mapper = getattr(obj, "__noesis_input_mapper__", None)

        def _policy_tag(self, intuition: Optional[Intuition]) -> str:
            if not intuition:
                return "None"
            name = intuition.__class__.__name__
            version = getattr(intuition, "__version__", None) or getattr(intuition, "version", None) or "unspecified"
            return f"{name}@{version}"

        def _apply_patch(self, inp: Any, patch: Dict[str, Any]) -> tuple[Any, bool, list[Dict[str, Any]], str]:
            """Apply a patch to input and compute diff."""
            if isinstance(inp, dict):
                out = deepcopy(inp)
                diff = []
                for k, v in patch.items():
                    diff.append({"key": k, "before": out.get(k), "after": v})
                    out[k] = v
                return out, True, diff, "applied"
            
            # Special case: rewrite string input with "rewrite" key in patch
            if isinstance(inp, str) and "rewrite" in patch:
                rewritten = str(patch["rewrite"])
                diff = [{"key": "rewrite", "before": inp, "after": rewritten}]
                return rewritten, True, diff, "rewritten"
            
            return inp, False, [], "not_patchable_input"

        def execute(
            self,
            *,
            task: str,
            episode_id: str,
            run_dir: Path,
            intuition: Optional[Intuition] = None,
            seed: int = 0,
            tags: Optional[Dict[str, Any]] = None,
        ) -> Any:
            policy = self._policy_tag(intuition)
            directive: Optional[IntuitionEvent] = None

            # Get input object (may be mapped)
            if self._input_mapper:
                input_obj = self._input_mapper(task)
            else:
                input_obj = task

            # Handle intuition/direction
            if intuition:
                snapshot = {
                    "task": task,
                    "seed": seed,
                    "history": [],
                    "tools_seen": [],
                    "tags": tags or {},
                }
                directive = intuition.advise(snapshot)

            if directive:
                # Emit intuition event
                write_event(
                    run_dir,
                    {
                        "id": str(uuid4()),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "episode_id": episode_id,
                        "agent_id": "adapter.callable",
                        "phase": "intuition",
                        "payload": {
                            "kind": directive.kind,
                            "advice": directive.advice,
                            "confidence": directive.confidence,
                            "applied": directive.applied,
                            "rationale": directive.rationale,
                            "target": directive.target,
                            "scope": directive.scope,
                            "blocking": directive.blocking,
                            "patch_keys": sorted(directive.patch.keys()) if directive.patch else [],
                            "policy": policy,
                        },
                        "evidence_ids": [],
                    },
                )

                # Handle direction based on directive kind
                payload: Dict[str, Any] = {
                    "kind": directive.kind,
                    "advice": directive.advice,
                    "confidence": directive.confidence,
                    "target": directive.target,
                    "scope": directive.scope,
                    "policy": policy,
                    "threshold": self._min_conf,
                }

                # Handle veto
                if directive.blocking or directive.kind == DirectiveKind.VETO.value:
                    payload.update({"applied": False, "status": "blocked", "reason": "veto"})
                    direction_event(run_dir, episode_id, payload, agent=policy)
                    raise NoesisVeto(advice=directive.advice, target=directive.target, scope=directive.scope)

                # Handle intervention
                if directive.kind == DirectiveKind.INTERVENTION.value:
                    patch = directive.patch or {}
                    if directive.confidence < self._min_conf:
                        payload.update({"applied": False, "patch": patch, "reason": "policy_low_confidence", "diff": []})
                        direction_event(run_dir, episode_id, payload, agent=policy)
                    elif not patch:
                        payload.update({"applied": False, "patch": {}, "reason": "empty_patch", "diff": []})
                        direction_event(run_dir, episode_id, payload, agent=policy)
                    else:
                        adjusted, applied, diff, reason = self._apply_patch(input_obj, patch)
                        payload.update({"applied": applied, "patch": patch, "reason": reason, "diff": diff})
                        direction_event(run_dir, episode_id, payload, agent=policy)
                        if applied:
                            input_obj = adjusted

            # Execute graph with (possibly patched) input
            if hasattr(self.obj, "invoke"):
                return self.obj.invoke(input_obj)
            if hasattr(self.obj, "run"):
                return self.obj.run(input_obj)
            if callable(self.obj):
                return self.obj(input_obj)
            raise TypeError("object is neither runnable nor callable")

    return _CallableAdapter(graph_obj, min_confidence)


# Public API

def set(*, context: RuntimeContext | None = None, **overrides: Any) -> None:
    app = context or get_context()
    config_port = app.require("config", getattr(app.config_port, "__api_version__", "config/1.0-rc1"))
    config_port.set(**overrides)


def solve(
    task: str,
    *,
    using: GraphSource,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
    context: RuntimeContext | None = None,
    determinism: "_DeterminismConfig | None" = None,
) -> str:
    app = context or get_context()
    return run_using(
        using=using,
        task=task,
        seed=seed,
        intuition=intuition,
        tags=tags,
        context=app,
        determinism=determinism,
    )


@dataclass(slots=True)
class _EpCtx:
    ids: EpisodeIds
    run_dir: Path
    started_at: str

    @property
    def episode_id(self) -> str:
        return self.ids.episode_id


@dataclass(slots=True)
class _EpisodeRuntime:
    cfg: Any
    port_versions: Any
    runs_dir: str
    dir_min: float
    ctx: _EpCtx
    episode_ctx: EpisodeContext
    state_repo: RuntimeStateRepository
    state: Any
    state_path: Path
    adapter_label: str
    raw_using_label: str
    determinism: "_DeterminismConfig | None"
    now_fn: Callable[[], str]
    run_clock: RuntimeClock | None
    event_id_factory: Callable[[], Any] | None
    intuition_impl: Intuition
    intuition_enabled: bool
    runtime_context: RuntimeContext


def _mint_episode_ids(seed: int, determinism: "_DeterminismConfig | None") -> EpisodeIds:
    if determinism:
        # Ensure deterministic ULID generation is not affected by prior runs.
        from .runtime.artifacts.ids import reset_ulid_state

        reset_ulid_state()
        return EpisodeIds.mint(
            seed=seed,
            timestamp_ms=determinism.episode_timestamp_ms,
            entropy=determinism.rng.bytes(10),
        )
    return EpisodeIds.mint(seed=seed)


def _parse_governance_mode(raw: object) -> GovernanceMode:
    """Coerce arbitrary input into a GovernanceMode enum."""
    if raw is None:
        return GovernanceMode.OFF
    if isinstance(raw, GovernanceMode):
        return raw
    s = str(raw).strip().lower()
    if "." in s:
        s = s.split(".")[-1]
    return GovernanceMode(s)


def _parse_governance_failure_policy(raw: object, mode: GovernanceMode) -> GovernanceFailurePolicy:
    """Coerce arbitrary input into a GovernanceFailurePolicy, with mode default."""
    if raw is None:
        return GovernanceFailurePolicy.default_for(mode)
    if isinstance(raw, GovernanceFailurePolicy):
        return raw
    s = str(raw).strip().lower()
    if "." in s:
        s = s.split(".")[-1]
    return GovernanceFailurePolicy(s)


def _init_clock(determinism: "_DeterminismConfig | None") -> tuple[RuntimeClock | None, Callable[[], str]]:
    if determinism:
        from noesis.runtime.determinism import DeterministicClock

        run_clock = DeterministicClock(
            start_at=determinism.clock.start_at,
            tick_ms=determinism.clock.tick_ms,
        )
        return run_clock, lambda: run_clock.now().isoformat()
    return None, _now


def _build_snapshot(
    *,
    task: str,
    seed: int,
    tags: Optional[Dict[str, Any]],
    state: Any,
    state_path: Path,
    run_dir: Path,
    raw_using_label: str,
) -> Dict[str, Any]:
    return {
        "task": task,
        "seed": seed,
        "history": [],
        "tools_seen": [],
        "tags": tags or {},
        "state_path": str(state_path.relative_to(run_dir)),
        "state": state.to_dict(),
        "using": raw_using_label,
    }


def _build_runner_ports(setup: _EpisodeRuntime) -> tuple[RuntimeEventBus, EpisodeInstrumentation, LineageTracker]:
    """Construct event bus + instrumentation using deterministic-friendly defaults."""
    lineage = LineageTracker()
    clock = setup.run_clock or RuntimeClock()
    now_fn = clock.now if setup.determinism else (lambda: datetime.now(timezone.utc))
    event_id_factory = setup.event_id_factory or uuid4
    emitter = CognitiveEventEmitter(run_dir=setup.ctx.run_dir)
    event_bus = RuntimeEventBus(
        context=setup.episode_ctx,
        emitter=emitter,
        lineage=lineage,
        clock=clock,
        now=now_fn,
        event_id_factory=event_id_factory,
    )
    instrumentation = EpisodeInstrumentation(
        clock=clock,
        emitter=emitter,
        lineage=lineage,
        prompt_recorder=setup.episode_ctx.prompt_recorder,
        now=now_fn,
        event_id_factory=event_id_factory,
        hooks=(),
    )
    return event_bus, instrumentation, lineage


def _finalize_episode(
    *,
    setup: _EpisodeRuntime,
    state: Any,
    task: str,
    seed: int,
    tags: Optional[Dict[str, Any]],
    status: str,
) -> None:
    _finalize_summary(
        run_dir=setup.ctx.run_dir,
        episode_id=setup.ctx.episode_id,
        task=task,
        seed=seed,
        started_at=setup.ctx.started_at,
        intuition_enabled=setup.intuition_enabled,
        intuition_mode=getattr(setup.intuition_impl, "mode", IntuitionMode.ADVISORY),
        using_label=setup.raw_using_label,
        tags=tags,
        intuition=setup.intuition_impl,
        schema_version=SCHEMA_VERSION,
        config=setup.cfg,
        ports=setup.port_versions,
    )

    persist_episode_memory(run_dir=setup.ctx.run_dir, context=setup.runtime_context)

    manifest_path, manifest_sha = _finalize_manifest(setup.ctx)

    try:
        store_root = Path(setup.runs_dir) / "_episodes"
        summary_path = setup.ctx.run_dir / "summary.json"
        EpisodeIndex(store_root, ttl_days=EPISODE_STORE_TTL_DAYS).append(
            episode_id=setup.ctx.episode_id,
            summary_path=summary_path,
            state_path=setup.state_path,
            status=status,
            task=task,
            using=setup.adapter_label,
            provenance={
                "schema_version": state.version,
                "state_schema_version": state.state_schema_version,
                "manifest_path": str(manifest_path),
                "manifest_sha256": manifest_sha,
                "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            },
        )
    except Exception:
        # Indexing is best-effort and should not fail the run.
        pass


def _bootstrap_episode(
    *,
    task: str,
    seed: int,
    tags: Optional[Dict[str, Any]],
    raw_using_label: str,
    adapter_label: str,
    context: RuntimeContext,
    intuition: bool | Intuition,
    determinism: "_DeterminismConfig | None",
) -> _EpisodeRuntime:
    config_port = context.require("config", getattr(context.config_port, "__api_version__", "config/1.0-rc1"))
    cfg = config_port.get()
    port_versions = context.list_ports()
    runs_dir = str(cfg.runs_dir)
    dir_min = cfg.direction_min_confidence

    ids = _mint_episode_ids(seed, determinism)
    run_dir = begin_episode(runs_dir, ids.episode_id)
    run_clock, now_fn = _init_clock(determinism)
    ctx = _EpCtx(ids=ids, run_dir=run_dir, started_at=now_fn())
    intuition_impl, intuition_enabled = _normalize_intuition(cfg.intuition_mode, intuition)

    episode_ctx = EpisodeContext(
        run_dir=ctx.run_dir,
        episode_id=ctx.episode_id,
        seed=seed,
        task=task,
        tags=tags or {},
        adapter_label=adapter_label,
        started_at=ctx.started_at,
        prompt_provenance_enabled=cfg.prompt_provenance_enabled,
        prompt_provenance_mode=cfg.prompt_provenance_mode,
    )
    episode_ctx.prompt_recorder = PromptRecorder.from_context(episode_ctx)
    state_repo = RuntimeStateRepository(context=episode_ctx)
    state = state_repo.init()
    state_path = ctx.run_dir / "state.json"

    event_id_factory = determinism.rng.event_id_factory(ids.directive_namespace) if determinism else None
    start_payload = {"task": task, "seed": seed, "using": raw_using_label}
    _start_event(
        ctx.run_dir,
        ctx.episode_id,
        start_payload,
        now_fn=now_fn if determinism else None,
        id_factory=event_id_factory,
    )

    return _EpisodeRuntime(
        cfg=cfg,
        port_versions=port_versions,
        runs_dir=runs_dir,
        dir_min=dir_min,
        ctx=ctx,
        episode_ctx=episode_ctx,
        state_repo=state_repo,
        state=state,
        state_path=state_path,
        adapter_label=adapter_label,
        raw_using_label=raw_using_label,
        determinism=determinism,
        now_fn=now_fn,
        run_clock=run_clock,
        event_id_factory=event_id_factory,
        intuition_impl=intuition_impl,
        intuition_enabled=intuition_enabled,
        runtime_context=context,
    )


def _run_minimal_episode(
    *,
    setup: _EpisodeRuntime,
    task: str,
    seed: int,
    tags: Optional[Dict[str, Any]],
) -> str:
    snapshot = _build_snapshot(
        task=task,
        seed=seed,
        tags=tags,
        state=setup.state,
        state_path=setup.state_path,
        run_dir=setup.ctx.run_dir,
        raw_using_label=setup.raw_using_label,
    )
    _observe_event(
        setup.ctx.run_dir,
        setup.ctx.episode_id,
        task=task,
        tags=tags,
        snapshot=snapshot,
        now_fn=setup.now_fn if setup.determinism else None,
        id_factory=setup.event_id_factory,
    )
    _maybe_intuition(
        setup.ctx.run_dir,
        setup.ctx.episode_id,
        setup.intuition_enabled,
        setup.intuition_impl,
        snapshot,
        now_fn=setup.now_fn if setup.determinism else None,
        id_factory=setup.event_id_factory,
    )

    event_bus, instrumentation, lineage = _build_runner_ports(setup)
    direction_planner = MetaPlanner() if setup.cfg.planner_mode is PlannerMode.META else None
    governance_mode = _parse_governance_mode(getattr(setup.cfg, "governance_mode", GovernanceMode.OFF))
    governance_policy = PreActGovernor() if governance_mode != GovernanceMode.OFF else None
    governance_failure_policy = _parse_governance_failure_policy(
        getattr(setup.cfg, "governance_failure_policy", None),
        governance_mode,
    )
    governance_timeout_ms = getattr(setup.cfg, "governance_timeout_ms", None)
    deps = EpisodeDependencies(
        planner=MinimalPlanner(),
        actuator=MinimalActuator(tool_label=setup.adapter_label),
        event_bus=event_bus,
        state_repository=setup.state_repo,
        direction_planner=direction_planner,
        governance_policy=governance_policy,
        governance_mode=governance_mode,
        governance_failure_policy=governance_failure_policy,
        governance_timeout_ms=governance_timeout_ms,
    )
    runner = EpisodeRunner(deps, instrumentation=instrumentation)
    episode_request = EpisodeRequest(goal=task, beliefs=tuple(), context=setup.episode_ctx)
    result = runner.run(episode_request)

    status_payload: Dict[str, Any] = {"status": result.outcome.status}
    if result.outcome.summary:
        status_payload["message"] = result.outcome.summary

    existing_events = read_events(setup.ctx.run_dir)
    if not any(evt.get("phase") == "terminate" for evt in existing_events):
        _terminate_event(
            setup.ctx.run_dir,
            setup.ctx.episode_id,
            status_payload,
            now_fn=setup.now_fn if setup.determinism else None,
            id_factory=setup.event_id_factory,
        )

    state = result.state
    setup.state = state
    state.set_links(
        events="events.jsonl",
        summary="summary.json",
        learn="learn.jsonl",
        manifest="manifest.json",
    )
    setup.state_repo.persist(state)

    _finalize_episode(
        setup=setup,
        state=state,
        task=task,
        seed=seed,
        tags=tags,
        status=status_payload["status"],
    )

    return setup.ctx.episode_id


def _run_adapter_episode(
    *,
    setup: _EpisodeRuntime,
    task: str,
    seed: int,
    tags: Optional[Dict[str, Any]],
    using: Optional[GraphSource],
) -> str:
    _event_bus, instrumentation, _lineage = _build_runner_ports(setup)
    now_fn = setup.now_fn if setup.determinism else None
    id_factory = setup.event_id_factory or instrumentation.event_id_factory
    snapshot = _build_snapshot(
        task=task,
        seed=seed,
        tags=tags,
        state=setup.state,
        state_path=setup.state_path,
        run_dir=setup.ctx.run_dir,
        raw_using_label=setup.raw_using_label,
    )
    _observe_event(
        setup.ctx.run_dir,
        setup.ctx.episode_id,
        task=task,
        tags=tags,
        snapshot=snapshot,
        now_fn=now_fn,
        id_factory=id_factory,
    )
    _maybe_intuition(
        setup.ctx.run_dir,
        setup.ctx.episode_id,
        setup.intuition_enabled,
        setup.intuition_impl,
        snapshot,
        now_fn=now_fn,
        id_factory=id_factory,
    )

    _interpret_event(
        setup.ctx.run_dir,
        setup.ctx.episode_id,
        signals=[],
        reasons=None,
        source="system",
        now_fn=now_fn,
        id_factory=id_factory,
    )

    plan_steps = [setup.adapter_label]
    plan_rationale = "Execute adapter"
    plan_step_objs = _plan_steps_from_labels(plan_steps)
    setup.state.set_plan(steps=plan_step_objs, rationale=plan_rationale, source="system")
    setup.state_repo.persist(setup.state)
    snapshot["state"] = setup.state.to_dict()
    _plan_event(
        setup.ctx.run_dir,
        setup.ctx.episode_id,
        steps=plan_steps,
        rationale=plan_rationale,
        source="system",
        now_fn=now_fn,
        id_factory=id_factory,
    )

    status_payload: Dict[str, Any] = {"status": "ok"}
    reflect_reasons: List[str] = []
    result_excerpt = ""
    success = True
    input_excerpt = task[:EXCERPT_IN_LEN]

    if using is None:
        result_excerpt = "no_adapter"
        reflect_reasons.append("no_adapter")
    else:
        graph = _load_graph(using)
        adapter = _select_adapter(graph, setup.dir_min)
        try:
            result = adapter.execute(
                task=task,
                episode_id=setup.ctx.episode_id,
                run_dir=setup.ctx.run_dir,
                intuition=setup.intuition_impl if setup.intuition_enabled else None,
                seed=seed,
                tags=tags,
            )
            result_excerpt = str(result)[:EXCERPT_OUT_LEN]
            reflect_reasons.append("adapter_ok")
        except NoesisVeto as err:
            success = False
            status_payload = {"status": "blocked", "message": str(err)}
            reflect_reasons.append("veto")
        except Exception as err:  # noqa: BLE001
            success = False
            status_payload = {"status": "error", "message": str(err)}
            reflect_reasons.append("error")

    action_outcome = result_excerpt or status_payload["status"]

    _ensure_act_event(
        setup.ctx.run_dir,
        setup.ctx.episode_id,
        adapter_label=setup.adapter_label,
        input_excerpt=input_excerpt,
        outcome=action_outcome,
    )

    action_status = _normalize_outcome_status(status_payload["status"], success=success)
    setup.state.record_action(
        kind="adapter",
        tool=setup.adapter_label,
        input_excerpt=input_excerpt,
        result_status=action_status,
        step_id=plan_step_objs[-1].id if plan_step_objs else None,
    )

    _reflect_event(
        setup.ctx.run_dir,
        setup.ctx.episode_id,
        success=success,
        deltas=None,
        reasons=reflect_reasons,
        now_fn=now_fn,
        id_factory=id_factory,
    )

    setup.state.set_outcome(
        status=action_status,
        summary=status_payload.get("message"),
        metrics={"success": 1.0 if success else 0.0},
    )
    setup.state_repo.persist(setup.state)

    _finalize_episode(
        setup=setup,
        state=setup.state,
        task=task,
        seed=seed,
        tags=tags,
        status=setup.state.outcome_status,
    )

    return setup.ctx.episode_id


def _run_impl(
    *,
    task: str,
    seed: int,
    intuition: bool | Intuition,
    tags: Optional[Dict[str, Any]],
    using: Optional[GraphSource],
    context: RuntimeContext,
    determinism: "_DeterminismConfig | None",
) -> str:
    minimal_mode = using is None
    raw_using_label: Optional[str]
    if minimal_mode:
        raw_using_label = "core.minimal"
    else:
        raw_using_label = _safe_using_label(using) if using is not None else "core.null"
    adapter_label = f"adapter:{raw_using_label}"

    setup = _bootstrap_episode(
        task=task,
        seed=seed,
        tags=tags,
        raw_using_label=raw_using_label,
        adapter_label=adapter_label,
        context=context,
        intuition=intuition,
        determinism=determinism,
    )

    if minimal_mode:
        return _run_minimal_episode(setup=setup, task=task, seed=seed, tags=tags)
    return _run_adapter_episode(setup=setup, task=task, seed=seed, tags=tags, using=using)


def run(
    task: str,
    *,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
    context: RuntimeContext | None = None,
    determinism: "_DeterminismConfig | None" = None,
) -> str:
    app = context or get_context()
    return _run_impl(
        task=task,
        seed=seed,
        intuition=intuition,
        tags=tags,
        using=None,
        context=app,
        determinism=determinism,
    )


def run_using(
    *,
    using: GraphSource,
    task: str,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
    context: RuntimeContext | None = None,
    determinism: "_DeterminismConfig | None" = None,
) -> str:
    app = context or get_context()
    return _run_impl(
        task=task,
        seed=seed,
        intuition=intuition,
        tags=tags,
        using=using,
        context=app,
        determinism=determinism,
    )


def run_graph(
    kind: GraphSource,
    *,
    task: str,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
    context: RuntimeContext | None = None,
    determinism: "_DeterminismConfig | None" = None,
) -> str:
    return run_using(
        using=kind,
        task=task,
        seed=seed,
        intuition=intuition,
        tags=tags,
        context=context,
        determinism=determinism,
    )


_DeterminismConfig = None
if TYPE_CHECKING:
    from .runtime.session.models import DeterminismConfig as _DeterminismConfig
