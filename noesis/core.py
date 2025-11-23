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
from .domain.faculties.governance import PreActGovernor
from .infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from .interfaces.observability import RuntimeEventBus
from .interfaces.config import PlannerMode
from .trace.events import write_event
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
    config_port = context.require("config", getattr(context.config_port, "__api_version__", "config/1.0-rc1"))
    cfg = config_port.get()
    port_versions = context.list_ports()
    runs_dir = str(cfg.runs_dir)
    dir_min = cfg.direction_min_confidence

    if determinism:
        # Ensure deterministic ULID generation is not affected by prior runs.
        from .runtime.artifacts.ids import reset_ulid_state

        reset_ulid_state()
        ids = EpisodeIds.mint(
            seed=seed,
            timestamp_ms=determinism.episode_timestamp_ms,
            entropy=determinism.rng.bytes(10),
        )
    else:
        ids = EpisodeIds.mint(seed=seed)
    run_dir = begin_episode(runs_dir, ids.episode_id)
    # Create a fresh clock instance for each run to ensure determinism
    if determinism:
        from noesis.runtime.determinism import DeterministicClock
        run_clock = DeterministicClock(
            start_at=determinism.clock.start_at,
            tick_ms=determinism.clock.tick_ms,
        )
        now_str: Callable[[], str] = lambda: run_clock.now().isoformat()
    else:
        run_clock = None
        now_str = _now
    ctx = _EpCtx(ids=ids, run_dir=run_dir, started_at=now_str())

    intuition_impl, intuition_enabled = _normalize_intuition(cfg.intuition_mode, intuition)

    minimal_mode = using is None
    raw_using_label: Optional[str]
    if minimal_mode:
        raw_using_label = "core.minimal"
    else:
        raw_using_label = _safe_using_label(using) if using is not None else "core.null"
    adapter_label = f"adapter:{raw_using_label}"
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

    start_payload = {"task": task, "seed": seed, "using": raw_using_label}
    pre_event_id_factory = determinism.rng.event_id_factory(ids.directive_namespace) if determinism else None
    _start_event(ctx.run_dir, ctx.episode_id, start_payload, now_fn=now_str if determinism else None, id_factory=pre_event_id_factory)

    if minimal_mode:
        snapshot = {
            "task": task,
            "seed": seed,
            "history": [],
            "tools_seen": [],
            "tags": tags or {},
            "state_path": str(state_path.relative_to(ctx.run_dir)),
            "state": state.to_dict(),
            "using": raw_using_label,
        }
        _observe_event(
            ctx.run_dir,
            ctx.episode_id,
            task=task,
            tags=tags,
            snapshot=snapshot,
            now_fn=now_str if determinism else None,
            id_factory=pre_event_id_factory,
        )
        _maybe_intuition(
            ctx.run_dir,
            ctx.episode_id,
            intuition_enabled,
            intuition_impl,
            snapshot,
            now_fn=now_str if determinism else None,
            id_factory=pre_event_id_factory,
        )

        lineage = LineageTracker()
        # Use the run clock created earlier
        if determinism:
            clock = run_clock
        else:
            clock = RuntimeClock()
        emitter = CognitiveEventEmitter(run_dir=ctx.run_dir)
        event_bus = RuntimeEventBus(
            context=episode_ctx,
            emitter=emitter,
            lineage=lineage,
            clock=clock,
            now=clock.now if determinism else (lambda: datetime.now(timezone.utc)),
            event_id_factory=pre_event_id_factory or uuid4,
        )
        direction_planner = MetaPlanner() if cfg.planner_mode is PlannerMode.META else None
        governance_policy = PreActGovernor() if cfg.planner_mode is PlannerMode.META else None
        deps = EpisodeDependencies(
            planner=MinimalPlanner(),
            actuator=MinimalActuator(tool_label=adapter_label),
            event_bus=event_bus,
            state_repository=state_repo,
            direction_planner=direction_planner,
            governance_policy=governance_policy,
        )
        instrumentation = EpisodeInstrumentation(
            clock=clock,
            emitter=emitter,
            lineage=lineage,
            now=clock.now if determinism else (lambda: datetime.now(timezone.utc)),
            event_id_factory=pre_event_id_factory or uuid4,
            hooks=(),
        )
        runner = EpisodeRunner(deps, instrumentation=instrumentation)
        episode_request = EpisodeRequest(goal=task, beliefs=tuple(), context=episode_ctx)
        result = runner.run(episode_request)

        status_payload: Dict[str, Any] = {"status": result.outcome.status}
        if result.outcome.summary:
            status_payload["message"] = result.outcome.summary

        _terminate_event(
            ctx.run_dir,
            ctx.episode_id,
            status_payload,
            now_fn=now_str if determinism else None,
            id_factory=pre_event_id_factory,
        )

        state = result.state
        state.set_links(
            events="events.jsonl",
            summary="summary.json",
            learn="learn.jsonl",
            manifest="manifest.json",
        )
        state_repo.persist(state)

        _finalize_summary(
            run_dir=ctx.run_dir,
            episode_id=ctx.episode_id,
            task=task,
            seed=seed,
            started_at=ctx.started_at,
            intuition_enabled=intuition_enabled,
            intuition_mode=getattr(intuition_impl, "mode", IntuitionMode.ADVISORY),
            using_label=raw_using_label,
            tags=tags,
            intuition=intuition_impl,
            schema_version=SCHEMA_VERSION,
            config=cfg,
            ports=port_versions,
        )

        persist_episode_memory(run_dir=ctx.run_dir, context=context)

        manifest_path, manifest_sha = _finalize_manifest(ctx)

        try:
            store_root = Path(runs_dir) / "_episodes"
            summary_path = ctx.run_dir / "summary.json"
            EpisodeIndex(store_root, ttl_days=EPISODE_STORE_TTL_DAYS).append(
                episode_id=ctx.episode_id,
                summary_path=summary_path,
                state_path=state_path,
                status=status_payload["status"],
                task=task,
                using=adapter_label,
                provenance={
                    "schema_version": state.version,
                    "state_schema_version": state.state_schema_version,
                    "manifest_path": str(manifest_path),
                    "manifest_sha256": manifest_sha,
                    "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
                },
            )
        except Exception:
            pass

        return ctx.episode_id

    # External adapter path continues below.
    snapshot = {
        "task": task,
        "seed": seed,
        "history": [],
        "tools_seen": [],
        "tags": tags or {},
        "state_path": str(state_path.relative_to(ctx.run_dir)),
        "state": state.to_dict(),
        "using": raw_using_label,
    }

    _observe_event(ctx.run_dir, ctx.episode_id, task=task, tags=tags, snapshot=snapshot)
    _maybe_intuition(ctx.run_dir, ctx.episode_id, intuition_enabled, intuition_impl, snapshot)

    _interpret_event(
        ctx.run_dir,
        ctx.episode_id,
        signals=[],
        reasons=None,
        source="system",
    )

    plan_steps = [adapter_label]
    plan_rationale = "Execute adapter"
    plan_step_objs = _plan_steps_from_labels(plan_steps)
    state.set_plan(steps=plan_step_objs, rationale=plan_rationale, source="system")
    state_repo.persist(state)
    snapshot["state"] = state.to_dict()
    _plan_event(ctx.run_dir, ctx.episode_id, steps=plan_steps, rationale=plan_rationale, source="system")

    status_payload: Dict[str, Any] = {"status": "ok"}
    reflect_reasons: List[str] = []
    result_excerpt = ""
    success = True
    veto_error: Optional[NoesisVeto] = None

    input_excerpt = task[:EXCERPT_IN_LEN]

    if using is None:
        result_excerpt = "no_adapter"
        reflect_reasons.append("no_adapter")
    else:
        graph = _load_graph(using)
        adapter = _select_adapter(graph, dir_min)
        try:
            result = adapter.execute(
                task=task,
                episode_id=ctx.episode_id,
                run_dir=ctx.run_dir,
                intuition=intuition_impl if intuition_enabled else None,
                seed=seed,
                tags=tags,
            )
            result_excerpt = str(result)[:EXCERPT_OUT_LEN]
            reflect_reasons.append("adapter_ok")
        except NoesisVeto as err:
            success = False
            status_payload = {"status": "blocked", "message": str(err)}
            veto_error = err
            reflect_reasons.append("veto")
        except Exception as err:  # noqa: BLE001
            success = False
            status_payload = {"status": "error", "message": str(err)}
            reflect_reasons.append("error")

    action_outcome = result_excerpt or status_payload["status"]

    _ensure_act_event(
        ctx.run_dir,
        ctx.episode_id,
        adapter_label=adapter_label,
        input_excerpt=input_excerpt,
        outcome=action_outcome,
    )

    action_status = _normalize_outcome_status(status_payload["status"], success=success)
    state.record_action(
        kind="adapter",
        tool=adapter_label,
        input_excerpt=input_excerpt,
        result_status=action_status,
        step_id=plan_step_objs[-1].id if plan_step_objs else None,
    )

    _reflect_event(
        ctx.run_dir,
        ctx.episode_id,
        success=success,
        deltas=None,
        reasons=reflect_reasons,
    )

    # Summarize and persist outcome
    state.set_outcome(
        status=action_status,
        summary=status_payload.get("message"),
        metrics={"success": 1.0 if success else 0.0},
    )
    state_repo.persist(state)

    _finalize_summary(
        run_dir=ctx.run_dir,
        episode_id=ctx.episode_id,
        task=task,
        seed=seed,
        started_at=ctx.started_at,
        intuition_enabled=intuition_enabled,
        intuition_mode=getattr(intuition_impl, "mode", IntuitionMode.ADVISORY),
        using_label=raw_using_label,
        tags=tags,
        intuition=intuition_impl,
        schema_version=SCHEMA_VERSION,
        config=cfg,
        ports=port_versions,
    )

    persist_episode_memory(run_dir=ctx.run_dir, context=context)

    manifest_path, manifest_sha = _finalize_manifest(ctx)

    try:
        store_root = Path(runs_dir) / "_episodes"
        summary_path = ctx.run_dir / "summary.json"
        EpisodeIndex(store_root, ttl_days=EPISODE_STORE_TTL_DAYS).append(
            episode_id=ctx.episode_id,
            summary_path=summary_path,
            state_path=state_path,
            status=state.outcome_status,
            task=task,
            using=adapter_label,
            provenance={
                "schema_version": state.version,
                "state_schema_version": state.state_schema_version,
                "manifest_path": str(manifest_path),
                "manifest_sha256": manifest_sha,
                "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
            },
        )
    except Exception:
        pass

    return ctx.episode_id


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
