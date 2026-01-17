"""
Execution core for Noēsis.

Responsibilities
    • Entry points: run(), solve(), run_using(), run_graph() (compat), set()
    • Orchestration: create episode IDs/dirs, emit start/terminate events
    • Intuition: normalize policy/mode for EpisodeRunner wiring
    • Adapters: load graph and select the appropriate actuator
    • Summarization: read events → compute metrics → write summary.json with flags

Key invariants
    - Every episode yields a well-formed events.jsonl and summary.json (success, error, or veto).
    - Intuition is optional; when disabled, core behavior is still fully traceable.
    - EpisodeRunner owns cognitive phase boundaries and governance ordering.

Schema
    SCHEMA_VERSION declares the summary schema version baked into artifacts.

Architecture notes
    - _run_impl sets up determinism/context and delegates to _run_episode.
    - EpisodeRunner emits observe → intuition → interpret → plan → direction → governance → act.
    - _finalize_episode centralizes artifact writes (summary, manifest, index).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Final, TYPE_CHECKING, Callable
from uuid import uuid4
from .domain.state import LineageTracker
from .state.episode import begin_episode
from .episode import EpisodeIndex
# Domain / use-case layer imports
from .domain.planner.minimal import MinimalActuator, MinimalPlanner
from .domain.planner.meta import MetaPlanner
from .domain.faculties.governance import GovernanceFailurePolicy, GovernanceMode, PreActGovernor
from .infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from .infrastructure.process_registry import FileProcessRegistry
from .domain.process import ProcessKind, derive_process_identity
from .infrastructure.snapshot import FileSystemSnapshotGateway, FileSystemSnapshotMetadataStore, UtcSnapshotClock
from .infrastructure.verification import FileSystemFileReader
from .interfaces.observability import RuntimeEventBus
from .interfaces.config import PlannerMode
from .trace.events import read_events, is_terminate_event
from .intuition import Intuition, NullIntuition, IntuitionMode
from .loader import load_graph, GraphSource
from .runtime.utils import now as _now
from .runtime.clock import RuntimeClock
from .runtime.events_emitter import CognitiveEventEmitter
from .runtime.prompt_recorder import PromptRecorder
from .runtime.events import start_event as _start_event, terminate_event as _terminate_event
from .runtime.normalization import normalize_using
from .runtime.summary import finalize_summary as _finalize_summary
from .runtime.learning import ensure_learn_file
from .trace.schema import SUMMARY_SCHEMA_VERSION
from .runtime.artifacts.ids import EpisodeIds
from .runtime.artifacts.writer import ManifestWriter
from .runtime.artifacts.manifest import MANIFEST_SCHEMA_VERSION, MANIFEST_FILE_NAME, compute_sha256
from .runtime.paths import NoesisPaths
from .usecases.episode_runner import (
    EpisodeDependencies,
    EpisodeInstrumentation,
    EpisodeRequest,
    EpisodeRunner,
)
from .verification import VerifyInput, normalize_verify
from .usecases.snapshot_artifacts import SnapshotArtifactWriter
from .usecases.memory_sync import persist_episode_memory
from .usecases.process_registry import ProcessRegistryService
from .domain.process import derive_process_identity
from .context import RuntimeContext, get_context

if TYPE_CHECKING:
    from .runtime.session.models import DeterminismConfig

SCHEMA_VERSION: Final[str] = SUMMARY_SCHEMA_VERSION
EPISODE_STORE_TTL_DAYS: Final[int] = 30


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


def _workspace_identity(workspace: Path | str | None) -> str:
    if workspace is None:
        return str(Path.cwd().resolve())
    return str(Path(workspace).expanduser().resolve())


# Public API

def set(*, context: RuntimeContext | None = None, **overrides: Any) -> None:
    from .runtime.actuation_registry import apply_actuation_overrides

    app = context or get_context()
    remaining = apply_actuation_overrides(overrides)
    if not remaining:
        return
    config_port = app.require("config", getattr(app.config_port, "__api_version__", "config/1.0-rc1"))
    config_port.set(**remaining)


def solve(
    task: str,
    *,
    using: GraphSource,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
    context: RuntimeContext | None = None,
    workspace: str | Path | None = None,
    process: str | None = None,
    verify: VerifyInput = None,
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
        workspace=workspace,
        verify=verify,
        determinism=determinism,
        process_name=process,
    )


async def solve_async(
    task: str,
    *,
    using: GraphSource,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
    context: RuntimeContext | None = None,
    workspace: str | Path | None = None,
    process: str | None = None,
    verify: VerifyInput = None,
    determinism: "_DeterminismConfig | None" = None,
) -> str:
    app = context or get_context()
    return await run_using_async(
        using=using,
        task=task,
        seed=seed,
        intuition=intuition,
        tags=tags,
        context=app,
        workspace=workspace,
        verify=verify,
        determinism=determinism,
        process_name=process,
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
    layout: NoesisPaths
    ctx: _EpCtx
    episode_ctx: EpisodeContext
    state_repo: RuntimeStateRepository
    state_path: Path
    adapter_label: str
    raw_using_label: str
    process_id: str
    process_name: str
    process_kind: ProcessKind
    process_run_index: int
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
    adapter_result: str,
    outcome: str,
    verification: Dict[str, object | None],
) -> None:
    process_block: Dict[str, object] | None = None
    if setup.episode_ctx.process_id:
        process_block = {
            "id": setup.episode_ctx.process_id,
            "name": setup.episode_ctx.process_name,
            "kind": setup.episode_ctx.process_kind,
            "run_index": setup.episode_ctx.process_run_index,
        }

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
        process_id=setup.process_id,
        process_name=setup.process_name,
        process_kind=setup.process_kind,
        process_run_index=setup.process_run_index,
        schema_version=SCHEMA_VERSION,
        config=setup.cfg,
        ports=setup.port_versions,
        adapter_result=adapter_result,
        outcome=outcome,
        verification=verification,
        process=process_block,
    )

    persist_episode_memory(run_dir=setup.ctx.run_dir, context=setup.runtime_context)

    manifest_path, manifest_sha = _finalize_manifest(setup.ctx)

    try:
        store_root = setup.layout.episodes_dir / "_episodes"
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

    try:
        process_id = setup.episode_ctx.process_id
        if process_id:
            factory = setup.runtime_context.require("process_registry_factory", "process_registry_factory/1.0")
            service = ProcessRegistryService(factory.create(setup.layout))
            status = "error" if outcome == "error" else "idle"
            service.end_run(
                process_id,
                run_id=setup.ctx.episode_id,
                outcome=outcome,
                status=status,
            )
    except Exception:
        # Registry updates should not prevent artifact completion.
        pass


def _bootstrap_episode(
    *,
    task: str,
    seed: int,
    tags: Optional[Dict[str, Any]],
    raw_using_label: str,
    adapter_label: str,
    context: RuntimeContext,
    workspace: str | Path | None,
    verify: VerifyInput,
    intuition: bool | Intuition,
    determinism: "_DeterminismConfig | None",
    process_name: str | None = None,
) -> _EpisodeRuntime:
    config_port = context.require("config", getattr(context.config_port, "__api_version__", "config/1.0-rc1"))
    cfg = config_port.get()
    port_versions = context.list_ports()
    workspace_path = Path(workspace).expanduser().resolve() if workspace is not None else None
    layout_port = context.require("layout", "layout/1.0")
    layout = layout_port.resolve(workspace=workspace_path, runs_dir=cfg.runs_dir)
    layout_port.ensure(layout)
    runs_dir = str(layout.episodes_dir)
    ids = _mint_episode_ids(seed, determinism)
    run_dir = begin_episode(runs_dir, ids.episode_id)
    run_clock, now_fn = _init_clock(determinism)
    ctx = _EpCtx(ids=ids, run_dir=run_dir, started_at=now_fn())
    intuition_impl, intuition_enabled = _normalize_intuition(cfg.intuition_mode, intuition)
    verify_specs = normalize_verify(verify)
    workspace_identity_path = workspace_path or Path(cfg.runs_dir).expanduser().resolve().parent
    identity = derive_process_identity(workspace_identity=str(workspace_identity_path), process_name=process_name)
    factory = context.require("process_registry_factory", "process_registry_factory/1.0")
    process_service = ProcessRegistryService(factory.create(layout))
    process_record = process_service.get_or_create(identity, kind="oneshot")
    process_record = process_service.start_run(process_record.process_id, run_id=ids.episode_id)

    episode_ctx = EpisodeContext(
        run_dir=ctx.run_dir,
        episode_id=ctx.episode_id,
        seed=seed,
        task=task,
        tags=tags or {},
        adapter_label=adapter_label,
        started_at=ctx.started_at,
        process_id=process_record.process_id,
        process_name=process_record.process_name,
        process_kind=process_record.kind,
        process_run_index=process_record.run_index,
        workspace=workspace_path,
        verify=verify_specs,
        intuition_mode=cfg.intuition_mode,
        prompt_provenance_enabled=cfg.prompt_provenance_enabled,
        prompt_provenance_mode=cfg.prompt_provenance_mode,
    )
    episode_ctx.prompt_recorder = PromptRecorder.from_context(episode_ctx)
    state_repo = RuntimeStateRepository(context=episode_ctx)
    state_path = ctx.run_dir / "state.json"

    event_id_factory = determinism.rng.event_id_factory(ids.directive_namespace) if determinism else None
    using_norm = normalize_using(raw_using_label)
    start_payload = {"task": task, "seed": seed, "using": using_norm.display if using_norm else raw_using_label}
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
        layout=layout,
        ctx=ctx,
        episode_ctx=episode_ctx,
        state_repo=state_repo,
        state_path=state_path,
        adapter_label=adapter_label,
        raw_using_label=raw_using_label,
        process_id=process_record.process_id,
        process_name=process_record.process_name,
        process_kind=process_record.kind,
        process_run_index=process_record.run_index,
        determinism=determinism,
        now_fn=now_fn,
        run_clock=run_clock,
        event_id_factory=event_id_factory,
        intuition_impl=intuition_impl,
        intuition_enabled=intuition_enabled,
        runtime_context=context,
    )


def _run_episode(
    *,
    setup: _EpisodeRuntime,
    task: str,
    seed: int,
    tags: Optional[Dict[str, Any]],
    using: Optional[GraphSource],
) -> str:
    event_bus, instrumentation, _lineage = _build_runner_ports(setup)
    direction_planner = MetaPlanner() if setup.cfg.planner_mode == PlannerMode.META else None
    governance_mode = _parse_governance_mode(getattr(setup.cfg, "governance_mode", GovernanceMode.OFF))
    governance_policy = PreActGovernor() if governance_mode != GovernanceMode.OFF else None
    governance_failure_policy = _parse_governance_failure_policy(
        getattr(setup.cfg, "governance_failure_policy", None),
        governance_mode,
    )
    governance_timeout_ms = getattr(setup.cfg, "governance_timeout_ms", None)

    if using is None:
        actuator = MinimalActuator(tool_label=setup.adapter_label)
    else:
        from noesis.infrastructure.episode.adapter_actuator import AdapterActuator

        graph = _load_graph(using)
        actuator = AdapterActuator(graph=graph, tool_label=setup.adapter_label)

    snapshot_writer = SnapshotArtifactWriter(
        gateway=FileSystemSnapshotGateway(),
        metadata_store=FileSystemSnapshotMetadataStore(),
        clock=UtcSnapshotClock(),
    )
    file_reader_factory = lambda root: FileSystemFileReader(root=root)
    deps = EpisodeDependencies(
        planner=MinimalPlanner(),
        actuator=actuator,
        event_bus=event_bus,
        state_repository=setup.state_repo,
        snapshot_writer=snapshot_writer,
        file_reader_factory=file_reader_factory,
        direction_planner=direction_planner,
        governance_policy=governance_policy,
        governance_mode=governance_mode,
        governance_failure_policy=governance_failure_policy,
        governance_timeout_ms=governance_timeout_ms,
        intuition_policy=setup.intuition_impl,
        intuition_enabled=setup.intuition_enabled,
    )
    runner = EpisodeRunner(deps, instrumentation=instrumentation)
    using_norm = normalize_using(setup.raw_using_label)
    using_label = using_norm.display if using_norm else setup.raw_using_label
    episode_request = EpisodeRequest(
        goal=task,
        beliefs=tuple(),
        context=setup.episode_ctx,
        using_label=using_label,
    )
    result = runner.run(episode_request)

    status_value = str(result.outcome.status or "unknown")
    default_message = "Episode terminated."
    message_raw = result.outcome.summary
    message_value = str(message_raw).strip() if message_raw else ""
    if not message_value:
        message_value = f"{status_value}." if status_value != "unknown" else default_message
    status_payload: Dict[str, Any] = {
        "status": status_value,
        "message": message_value,
    }

    existing_events = read_events(setup.ctx.run_dir)
    if not any(is_terminate_event(evt) for evt in existing_events):
        _terminate_event(
            setup.ctx.run_dir,
            setup.ctx.episode_id,
            status_payload,
            now_fn=setup.now_fn if setup.determinism else None,
            id_factory=setup.event_id_factory,
        )

    state = result.state
    ensure_learn_file(setup.ctx.run_dir)
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
        adapter_result=result.adapter_result,
        outcome=result.verification_outcome,
        verification=result.verification,
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
    workspace: str | Path | None,
    verify: VerifyInput,
    determinism: "_DeterminismConfig | None",
    process_name: str | None = None,
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
        workspace=workspace,
        verify=verify,
        intuition=intuition,
        determinism=determinism,
        process_name=process_name,
    )

    return _run_episode(setup=setup, task=task, seed=seed, tags=tags, using=using)


async def _run_episode_async(
    *,
    setup: _EpisodeRuntime,
    task: str,
    seed: int,
    tags: Optional[Dict[str, Any]],
    using: Optional[GraphSource],
) -> str:
    event_bus, instrumentation, _lineage = _build_runner_ports(setup)
    direction_planner = MetaPlanner() if setup.cfg.planner_mode == PlannerMode.META else None
    governance_mode = _parse_governance_mode(getattr(setup.cfg, "governance_mode", GovernanceMode.OFF))
    governance_policy = PreActGovernor() if governance_mode != GovernanceMode.OFF else None
    governance_failure_policy = _parse_governance_failure_policy(
        getattr(setup.cfg, "governance_failure_policy", None),
        governance_mode,
    )
    governance_timeout_ms = getattr(setup.cfg, "governance_timeout_ms", None)

    if using is None:
        actuator = MinimalActuator(tool_label=setup.adapter_label)
    else:
        from noesis.infrastructure.episode.adapter_actuator import AsyncAdapterActuator

        graph = _load_graph(using)
        actuator = AsyncAdapterActuator(graph=graph, tool_label=setup.adapter_label)

    deps = EpisodeDependencies(
        planner=MinimalPlanner(),
        actuator=actuator,
        event_bus=event_bus,
        state_repository=setup.state_repo,
        direction_planner=direction_planner,
        governance_policy=governance_policy,
        governance_mode=governance_mode,
        governance_failure_policy=governance_failure_policy,
        governance_timeout_ms=governance_timeout_ms,
        intuition_policy=setup.intuition_impl,
        intuition_enabled=setup.intuition_enabled,
    )
    runner = EpisodeRunner(deps, instrumentation=instrumentation)
    using_norm = normalize_using(setup.raw_using_label)
    using_label = using_norm.display if using_norm else setup.raw_using_label
    episode_request = EpisodeRequest(
        goal=task,
        beliefs=tuple(),
        context=setup.episode_ctx,
        using_label=using_label,
    )
    result = await runner.run_async(episode_request)

    status_value = str(result.outcome.status or "unknown")
    default_message = "Episode terminated."
    message_raw = result.outcome.summary
    message_value = str(message_raw).strip() if message_raw else ""
    if not message_value:
        message_value = f"{status_value}." if status_value != "unknown" else default_message
    status_payload: Dict[str, Any] = {
        "status": status_value,
        "message": message_value,
    }

    existing_events = read_events(setup.ctx.run_dir)
    if not any(is_terminate_event(evt) for evt in existing_events):
        _terminate_event(
            setup.ctx.run_dir,
            setup.ctx.episode_id,
            status_payload,
            now_fn=setup.now_fn if setup.determinism else None,
            id_factory=setup.event_id_factory,
        )

    state = result.state
    ensure_learn_file(setup.ctx.run_dir)
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
        adapter_result=result.adapter_result,
        outcome=result.verification_outcome,
        verification=result.verification,
    )

    return setup.ctx.episode_id


def run(
    task: str,
    *,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
    context: RuntimeContext | None = None,
    workspace: str | Path | None = None,
    verify: VerifyInput = None,
    determinism: "_DeterminismConfig | None" = None,
    process_name: str | None = None,
) -> str:
    app = context or get_context()
    workspace_path = Path(workspace) if workspace is not None else None
    verify_specs = normalize_verify(verify)
    return _run_impl(
        task=task,
        seed=seed,
        intuition=intuition,
        tags=tags,
        using=None,
        context=app,
        workspace=workspace_path,
        verify=verify_specs,
        determinism=determinism,
        process_name=process_name,
    )


def run_using(
    *,
    using: GraphSource,
    task: str,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
    context: RuntimeContext | None = None,
    workspace: str | Path | None = None,
    verify: VerifyInput = None,
    determinism: "_DeterminismConfig | None" = None,
    process_name: str | None = None,
) -> str:
    app = context or get_context()
    workspace_path = Path(workspace) if workspace is not None else None
    verify_specs = normalize_verify(verify)
    return _run_impl(
        task=task,
        seed=seed,
        intuition=intuition,
        tags=tags,
        using=using,
        context=app,
        workspace=workspace_path,
        verify=verify_specs,
        determinism=determinism,
        process_name=process_name,
    )


async def run_using_async(
    *,
    using: GraphSource,
    task: str,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
    context: RuntimeContext | None = None,
    workspace: str | Path | None = None,
    verify: VerifyInput = None,
    determinism: "_DeterminismConfig | None" = None,
    process_name: str | None = None,
) -> str:
    app = context or get_context()
    workspace_path = Path(workspace) if workspace is not None else None
    verify_specs = normalize_verify(verify)
    return await _run_impl_async(
        task=task,
        seed=seed,
        intuition=intuition,
        tags=tags,
        using=using,
        context=app,
        workspace=workspace_path,
        verify=verify_specs,
        determinism=determinism,
        process_name=process_name,
    )


async def _run_impl_async(
    *,
    task: str,
    seed: int,
    intuition: bool | Intuition,
    tags: Optional[Dict[str, Any]],
    using: Optional[GraphSource],
    context: RuntimeContext,
    workspace: str | Path | None,
    verify: VerifyInput,
    determinism: "_DeterminismConfig | None",
    process_name: str | None = None,
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
        workspace=workspace,
        verify=verify,
        intuition=intuition,
        determinism=determinism,
        process_name=process_name,
    )

    return await _run_episode_async(setup=setup, task=task, seed=seed, tags=tags, using=using)


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
