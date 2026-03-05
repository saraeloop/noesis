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
import threading
from uuid import uuid4
from .domain.state import LineageTracker
from .state.episode import begin_episode
from .episode import EpisodeIndex
# Domain / use-case layer imports
from .domain.planner.minimal import MinimalActuator, MinimalPlanner
from .domain.planner.meta import MetaPlanner
from .domain.faculties.governance import GovernanceFailurePolicy, GovernanceMode, PreActGovernor
from .infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
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
from .runtime.artifacts.manifest import MANIFEST_SCHEMA_VERSION, compute_sha256
from .runtime.artifacts.immutability import default_artifact_guard
from .runtime.paths import NoesisPaths
from .usecases.episode_runner import (
    EpisodeDependencies,
    EpisodeInstrumentation,
    EpisodeRequest,
    ResumeAnchor,
    EpisodeRunner,
)
from .verification import VerifyInput, normalize_verify
from .usecases.snapshot_artifacts import SnapshotArtifactWriter
from .usecases.memory_sync import persist_episode_memory
from .usecases.finalization import FinalizationWriter, map_outcome_to_final_contract
from .usecases.process_registry import ProcessRegistryService, STALE_TTL_SECONDS
from .usecases.run_lifecycle import create_run_lifecycle_service
from .domain.artifacts.finalization import FinalizationRecord, FINAL_FILE_NAME
from .domain.run_lifecycle import ResumeAdapterMismatchError, ResumeAdapterRequiredError
from .context import RuntimeContext, get_context

SCHEMA_VERSION: Final[str] = SUMMARY_SCHEMA_VERSION
EPISODE_STORE_TTL_DAYS: Final[int] = 30
_NONTERMINAL_RUN_STATUSES: frozenset[str] = frozenset({"interrupted", "paused"})


def _finalize_manifest(ctx: _EpCtx) -> tuple[Path, str]:
    writer = ManifestWriter(run_dir=ctx.run_dir, episode_id=ctx.episode_id)
    writer.finalize()
    digest = compute_sha256(writer.manifest_path)
    return writer.manifest_path, digest


def _seal_episode(
    *,
    ctx: _EpCtx,
    final_writer: FinalizationWriter,
    final_record: FinalizationRecord,
) -> tuple[Path, str]:
    """
    Seal an episode atomically at the contract level.

    Order:
    1) write final.json
    2) write manifest.json including final.json

    If manifest writing fails, remove final.json so the run is not marked sealed.
    """
    final_path = ctx.run_dir / FINAL_FILE_NAME
    final_writer.write(episode_dir=ctx.run_dir, record=final_record)
    try:
        return _finalize_manifest(ctx)
    except Exception:
        try:
            final_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def _update_process_run_status(
    *,
    setup: _EpisodeRuntime,
    run_id: str,
    outcome: str,
    status: str,
) -> None:
    try:
        process_id = setup.episode_ctx.process_id
        if process_id:
            factory = setup.runtime_context.require("process_registry_factory", "process_registry_factory/1.0")
            service = ProcessRegistryService(factory.create(setup.layout))
            service.end_run(
                process_id,
                run_id=run_id,
                outcome=outcome,
                status=status,
            )
    except Exception:
        # Registry updates should not prevent artifact completion.
        pass


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


def interrupt(
    episode_id: str,
    *,
    reason: str | None = None,
    caused_by: str | None = None,
    context: RuntimeContext | None = None,
    workspace: str | Path | None = None,
) -> str:
    """Emit a run interruption lifecycle event for an unsealed run."""
    app = context or get_context()
    workspace_path = Path(workspace).expanduser().resolve() if workspace is not None else None
    service = create_run_lifecycle_service(context=app, workspace=workspace_path)
    return service.interrupt(episode_id, reason=reason, caused_by=caused_by)


def checkpoint(
    episode_id: str,
    *,
    caused_by: str | None = None,
    context: RuntimeContext | None = None,
    workspace: str | Path | None = None,
) -> Dict[str, object]:
    """Create a deterministic checkpoint pointer for an unsealed run."""
    app = context or get_context()
    workspace_path = Path(workspace).expanduser().resolve() if workspace is not None else None
    service = create_run_lifecycle_service(context=app, workspace=workspace_path)
    return service.checkpoint(episode_id, caused_by=caused_by).to_dict()


def resume(
    episode_id: str,
    *,
    checkpoint_id: str,
    caused_by: str | None = None,
    context: RuntimeContext | None = None,
    workspace: str | Path | None = None,
) -> str:
    """Emit a run resume lifecycle event for an unsealed run checkpoint."""
    app = context or get_context()
    workspace_path = Path(workspace).expanduser().resolve() if workspace is not None else None
    service = create_run_lifecycle_service(context=app, workspace=workspace_path)
    return service.resume(episode_id, checkpoint_id=checkpoint_id, caused_by=caused_by)


def resume_run(
    episode_id: str,
    *,
    checkpoint_id: str,
    using: GraphSource | None = None,
    caused_by: str | None = None,
    context: RuntimeContext | None = None,
    workspace: str | Path | None = None,
    verify: VerifyInput = None,
    determinism: "_DeterminismConfig | None" = None,
) -> str:
    """Resume and continue execution on the same run from a checkpoint anchor."""
    app = context or get_context()
    workspace_path = Path(workspace).expanduser().resolve() if workspace is not None else None
    verify_specs = normalize_verify(verify)
    service = create_run_lifecycle_service(context=app, workspace=workspace_path)
    checkpoint = service.load_checkpoint_for_resume(
        episode_id,
        checkpoint_id=checkpoint_id,
    )
    setup = _bootstrap_resumed_episode(
        episode_id=episode_id,
        context=app,
        workspace=workspace_path,
        verify=verify_specs,
        determinism=determinism,
    )
    expected_using_raw = checkpoint.adapter_label or setup.raw_using_label
    expected_norm = normalize_using(expected_using_raw)
    expected_using_label = expected_norm.display if expected_norm else expected_using_raw
    if using is None:
        resolved_using_label = "core.minimal"
    else:
        resolved_raw = _safe_using_label(using)
        resolved_norm = normalize_using(resolved_raw)
        resolved_using_label = resolved_norm.display if resolved_norm else resolved_raw
    if using is None and expected_using_label != "core.minimal":
        raise ResumeAdapterRequiredError(
            "resume_run requires `using` for non-minimal runs; "
            f"checkpoint expects {expected_using_label!r}"
        )
    if resolved_using_label != expected_using_label:
        raise ResumeAdapterMismatchError(
            "resume_run adapter mismatch: "
            f"checkpoint expects {expected_using_label!r}, got {resolved_using_label!r}"
        )
    resume_event_id = service.resume(
        episode_id,
        checkpoint_id=checkpoint_id,
        caused_by=caused_by,
    )
    anchor = ResumeAnchor(
        checkpoint_id=checkpoint.checkpoint_id,
        state_hash=checkpoint.state_hash,
        last_event_id=checkpoint.last_event_id,
        resume_event_id=resume_event_id,
        event_offset=checkpoint.event_offset,
    )
    return _run_episode(
        setup=setup,
        task=setup.episode_ctx.task,
        seed=setup.episode_ctx.seed,
        tags=dict(setup.episode_ctx.tags),
        using=using,
        resume_anchor=anchor,
    )


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


def _start_process_heartbeat(setup: _EpisodeRuntime) -> tuple[threading.Event | None, threading.Thread | None]:
    process_id = setup.episode_ctx.process_id
    if not process_id:
        return None, None
    try:
        factory = setup.runtime_context.require("process_registry_factory", "process_registry_factory/1.0")
        service = ProcessRegistryService(factory.create(setup.layout))
    except Exception:
        return None, None
    interval = max(10, STALE_TTL_SECONDS // 2)
    stop_event = threading.Event()

    def _loop() -> None:
        while not stop_event.wait(interval):
            try:
                service.heartbeat(process_id)
            except Exception:
                pass

    thread = threading.Thread(target=_loop, name="noesis-process-heartbeat", daemon=True)
    thread.start()
    return stop_event, thread


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
    final_writer = FinalizationWriter(immutability_guard=default_artifact_guard())
    if setup.episode_ctx.process_id is None or setup.episode_ctx.process_run_index is None:
        raise ValueError("finalization requires process_id and run_index")
    final_outcome, verification_status = map_outcome_to_final_contract(
        outcome=outcome,
        terminal_status=status,
    )
    final_record = FinalizationRecord(
        episode_id=setup.ctx.episode_id,
        process_id=setup.episode_ctx.process_id,
        run_index=setup.episode_ctx.process_run_index,
        finalized_at=_now(),
        outcome=final_outcome,
        verification_status=verification_status,
    )

    try:
        manifest_path, manifest_sha = _seal_episode(
            ctx=setup.ctx,
            final_writer=final_writer,
            final_record=final_record,
        )
    except Exception:
        _update_process_run_status(
            setup=setup,
            run_id=setup.ctx.episode_id,
            outcome=outcome,
            status="error",
        )
        raise

    try:
        store_root = setup.layout.index_dir
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

    _update_process_run_status(
        setup=setup,
        run_id=setup.ctx.episode_id,
        outcome=outcome,
        status="error" if outcome == "error" else "idle",
    )


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


def _bootstrap_resumed_episode(
    *,
    episode_id: str,
    context: RuntimeContext,
    workspace: Path | None,
    verify: VerifyInput,
    determinism: "_DeterminismConfig | None",
) -> _EpisodeRuntime:
    """Rehydrate runtime setup for continuation on an existing run."""
    config_port = context.require("config", getattr(context.config_port, "__api_version__", "config/1.0-rc1"))
    cfg = config_port.get()
    port_versions = context.list_ports()
    workspace_path = workspace.expanduser().resolve() if workspace is not None else None
    layout_port = context.require("layout", "layout/1.0")
    layout = layout_port.resolve(workspace=workspace_path, runs_dir=cfg.runs_dir)
    layout_port.ensure(layout)

    lifecycle = create_run_lifecycle_service(context=context, workspace=workspace_path)
    run_dir = lifecycle.resolve_run_dir(episode_id)

    ids = EpisodeIds.from_episode(episode_id)
    run_clock, now_fn = _init_clock(determinism)
    event_id_factory = determinism.rng.event_id_factory(ids.directive_namespace) if determinism else None
    verify_specs = normalize_verify(verify)

    probe_ctx = EpisodeContext(
        run_dir=run_dir,
        episode_id=episode_id,
        seed=0,
        task="",
        tags={},
        # Empty adapter label intentionally allows state.json episode.using to win.
        adapter_label="",
        started_at=_now(),
        workspace=workspace_path,
        verify=verify_specs,
        intuition_mode=cfg.intuition_mode,
        prompt_provenance_enabled=cfg.prompt_provenance_enabled,
        prompt_provenance_mode=cfg.prompt_provenance_mode,
    )
    probe_state = RuntimeStateRepository(context=probe_ctx).init(probe_ctx)

    if probe_state.process_id is None or probe_state.process_run_index is None:
        raise ValueError("resume_run requires process metadata in state.json (process.id and process.run_index)")

    using_norm = normalize_using(probe_state.adapter_label)
    raw_using_label = using_norm.display if using_norm else probe_state.adapter_label

    episode_ctx = EpisodeContext(
        run_dir=run_dir,
        episode_id=episode_id,
        seed=probe_state.seed,
        task=probe_state.task,
        tags=dict(probe_state.tags),
        adapter_label=probe_state.adapter_label,
        started_at=probe_state.started_at,
        process_id=probe_state.process_id,
        process_name=probe_state.process_name,
        process_kind=probe_state.process_kind,
        process_run_index=probe_state.process_run_index,
        workspace=workspace_path,
        verify=verify_specs,
        intuition_mode=probe_state.intuition_mode,
        prompt_provenance_enabled=cfg.prompt_provenance_enabled,
        prompt_provenance_mode=cfg.prompt_provenance_mode,
    )
    episode_ctx.prompt_recorder = PromptRecorder.from_context(episode_ctx)
    state_repo = RuntimeStateRepository(context=episode_ctx)
    state_path = run_dir / "state.json"
    intuition_impl, intuition_enabled = _normalize_intuition(probe_state.intuition_mode, False)
    ctx = _EpCtx(ids=ids, run_dir=run_dir, started_at=probe_state.started_at)

    return _EpisodeRuntime(
        cfg=cfg,
        port_versions=port_versions,
        layout=layout,
        ctx=ctx,
        episode_ctx=episode_ctx,
        state_repo=state_repo,
        state_path=state_path,
        adapter_label=probe_state.adapter_label,
        raw_using_label=raw_using_label,
        process_id=probe_state.process_id,
        process_name=probe_state.process_name or "",
        process_kind=probe_state.process_kind or "oneshot",
        process_run_index=probe_state.process_run_index,
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
    resume_anchor: ResumeAnchor | None = None,
) -> str:
    stop_event, thread = _start_process_heartbeat(setup)
    try:
        event_bus, instrumentation, _lineage = _build_runner_ports(setup)
        direction_planner = MetaPlanner() if setup.cfg.planner_mode == PlannerMode.META else None
        governance_mode = _parse_governance_mode(getattr(setup.cfg, "governance_mode", GovernanceMode.OFF))
        governance_pause_on_veto = bool(getattr(setup.cfg, "governance_pause_on_veto", False))
        lifecycle_service = (
            create_run_lifecycle_service(context=setup.runtime_context, workspace=setup.episode_ctx.workspace)
            if governance_pause_on_veto
            else None
        )
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
            immutability_guard=default_artifact_guard(),
        )
        def file_reader_factory(root):
            return FileSystemFileReader(root=root)

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
            governance_pause_on_veto=governance_pause_on_veto,
            run_lifecycle=lifecycle_service,
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
        if resume_anchor is None:
            result = runner.run(episode_request)
        else:
            result = runner.resume(episode_request, anchor=resume_anchor)

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
        if status_value in _NONTERMINAL_RUN_STATUSES:
            state = result.state
            ensure_learn_file(setup.ctx.run_dir)
            state.set_links(
                events="events.jsonl",
                learn="learn.jsonl",
            )
            setup.state_repo.persist(state)
            return setup.ctx.episode_id

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
    finally:
        if stop_event is not None:
            stop_event.set()
        if thread is not None:
            thread.join(timeout=1.0)


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
    stop_event, thread = _start_process_heartbeat(setup)
    try:
        event_bus, instrumentation, _lineage = _build_runner_ports(setup)
        direction_planner = MetaPlanner() if setup.cfg.planner_mode == PlannerMode.META else None
        governance_mode = _parse_governance_mode(getattr(setup.cfg, "governance_mode", GovernanceMode.OFF))
        governance_pause_on_veto = bool(getattr(setup.cfg, "governance_pause_on_veto", False))
        lifecycle_service = (
            create_run_lifecycle_service(context=setup.runtime_context, workspace=setup.episode_ctx.workspace)
            if governance_pause_on_veto
            else None
        )
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

        snapshot_writer = SnapshotArtifactWriter(
            gateway=FileSystemSnapshotGateway(),
            metadata_store=FileSystemSnapshotMetadataStore(),
            clock=UtcSnapshotClock(),
            immutability_guard=default_artifact_guard(),
        )
        def file_reader_factory(root):
            return FileSystemFileReader(root=root)

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
            governance_pause_on_veto=governance_pause_on_veto,
            run_lifecycle=lifecycle_service,
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
        if status_value in _NONTERMINAL_RUN_STATUSES:
            state = result.state
            ensure_learn_file(setup.ctx.run_dir)
            state.set_links(
                events="events.jsonl",
                learn="learn.jsonl",
            )
            setup.state_repo.persist(state)
            return setup.ctx.episode_id

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
    finally:
        if stop_event is not None:
            stop_event.set()
        if thread is not None:
            thread.join(timeout=1.0)


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
