"""
Default governed actuation implementation.

Uses ADR-008 action candidates + pre-act governance to control side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from uuid import UUID, uuid4

from noesis.context import RuntimeContext
from noesis.domain.action_candidates import ActionCandidate, RedactionSpec
from noesis.domain.faculties.governance import GovernanceMode, PreActGovernor
from noesis.domain.state import LineageTracker, NoesisState
from noesis.exceptions import NoesisVeto
from noesis.infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from noesis.interfaces.actuation import ActuationPort, GovernedActRequest
from noesis.runtime.actuation_registry import get_actuation_registry
from noesis.runtime.artifacts.ids import EpisodeIds, reset_ulid_state
from noesis.runtime.artifacts.manifest import compute_sha256
from noesis.runtime.artifacts.writer import ManifestWriter
from noesis.runtime.clock import RuntimeClock
from noesis.runtime.events import start_event as _start_event, terminate_event as _terminate_event
from noesis.runtime.events_emitter import CognitiveEventEmitter
from noesis.runtime.learning import ensure_learn_file
from noesis.runtime.summary import finalize_summary as _finalize_summary
from noesis.domain.snapshot import DEFAULT_IGNORE, SnapshotPolicy
from noesis.domain.verification import VerificationSummary
from noesis.trace.schema import SUMMARY_SCHEMA_VERSION
from noesis.usecases.action_gating import govern_pre_act_action
from noesis.usecases.memory_sync import persist_episode_memory

if True:  # typing-only imports without runtime overhead
    from noesis.runtime.session.models import DeterminismConfig


_DEFAULT_REDACTION = RedactionSpec(
    mode="hash_only",
    policy_id="redact.default",
    policy_version="1.0.0",
    field_rules={},
)


@dataclass(slots=True)
class _GovernedActRuntime:
    run_dir: Path
    episode_id: str
    started_at: str
    event_id_factory: Callable[[], UUID]
    now_fn: Callable[[], str]
    clock: RuntimeClock
    state_repo: RuntimeStateRepository
    state: NoesisState
    adapter_label: str


class DefaultActuationPort(ActuationPort):
    """Default actuation port for governed actions."""

    __api_version__ = "actuation/1.0"

    def governed_act(self, request: GovernedActRequest, *, context: RuntimeContext) -> Any:
        return governed_act_impl(request=request, context=context)


def governed_act_impl(*, request: GovernedActRequest, context: RuntimeContext) -> Any:
    """
    Execute a governed action with a deterministic action-candidate boundary.
    """
    registry = get_actuation_registry()
    cfg = _config_snapshot(context)
    determinism = getattr(request, "determinism", None)
    runtime = _bootstrap_runtime(
        request=request,
        context=context,
        determinism=determinism,
        cfg=cfg,
    )
    candidate = _build_candidate(
        kind=request.kind,
        payload=request.payload,
        provenance=request.provenance,
        risk_tags=request.risk_tags,
        redaction=request.redaction,
        state_hash=_state_hash(runtime.run_dir),
    )

    gate = govern_pre_act_action(
        goal=request.goal,
        plan=(),
        candidate=candidate,
        event_bus=_event_bus(runtime),
        episode_id=runtime.episode_id,
        governance_policy=_resolve_policy(cfg.governance_mode, registry.governance_policy),
        governance_mode=cfg.governance_mode,
        failure_policy=cfg.governance_failure_policy,
        timeout_ms=cfg.governance_timeout_ms,
        caused_by=None,
    )

    if gate.terminal_outcome == "vetoed":
        _finalize_terminal(
            runtime=runtime,
            context=context,
            status="vetoed",
            message=_governance_message(gate),
        )
        raise _veto_exception(gate, request.kind)

    if gate.terminal_outcome == "error":
        _finalize_terminal(
            runtime=runtime,
            context=context,
            status="error",
            message=_governance_message(gate),
        )
        raise RuntimeError("governance_failure")

    executor = _resolve_executor(request.kind, registry)
    result: Any | None = None
    outcome = "ok"
    error: Exception | None = None
    try:
        result = _invoke_executor(executor, request.payload)
    except Exception as exc:  # noqa: BLE001
        outcome = "error"
        error = exc

    action = runtime.state.record_action(
        kind=request.kind,
        tool=_resolve_tool_label(request.kind, request.payload, runtime.adapter_label),
        input_excerpt=_input_excerpt(request.goal, request.payload),
        result_status=outcome,
        step_id=None,
        extensions={"x-action_candidate_id": gate.candidate.id},
    )
    bus = _event_bus(runtime)
    caused_by = gate.governance_event_id or gate.candidate_event_id
    bus.emit_action(action, caused_by=caused_by)

    status = "ok" if outcome == "ok" else "error"
    _finalize_terminal(
        runtime=runtime,
        context=context,
        status=status,
        message=_message_for_status(request.goal, outcome, error),
    )

    if error is not None:
        raise error
    return result


def _config_snapshot(context: RuntimeContext) -> Any:
    config_port = context.require(
        "config",
        getattr(context.config_port, "__api_version__", "config/1.0-rc1"),
    )
    return config_port.get()


def _bootstrap_runtime(
    *,
    request: GovernedActRequest,
    context: RuntimeContext,
    determinism: "DeterminismConfig | None",
    cfg: Any,
) -> _GovernedActRuntime:
    ids = _mint_episode_ids(request.seed, determinism)
    run_dir = _begin_episode(cfg.runs_dir, ids.episode_id)
    clock, now_fn = _init_clock(determinism)
    started_at = now_fn()
    adapter_label = _resolve_adapter_label(request.kind, request.payload)
    episode_ctx = EpisodeContext(
        run_dir=run_dir,
        episode_id=ids.episode_id,
        seed=request.seed,
        task=request.goal,
        tags=dict(request.tags or {}),
        adapter_label=adapter_label,
        started_at=started_at,
        intuition_mode=cfg.intuition_mode,
        prompt_provenance_enabled=getattr(cfg, "prompt_provenance_enabled", False),
        prompt_provenance_mode=getattr(cfg, "prompt_provenance_mode", "hash_only"),
    )
    state_repo = RuntimeStateRepository(context=episode_ctx)
    state = state_repo.init(episode_ctx)
    event_id_factory = determinism.rng.event_id_factory(ids.directive_namespace) if determinism else uuid4
    _start_event(
        run_dir,
        ids.episode_id,
        {"task": request.goal, "seed": request.seed, "using": adapter_label},
        now_fn=now_fn if determinism else None,
        id_factory=event_id_factory,
    )
    return _GovernedActRuntime(
        run_dir=run_dir,
        episode_id=ids.episode_id,
        started_at=started_at,
        event_id_factory=event_id_factory,
        now_fn=now_fn,
        clock=clock,
        state_repo=state_repo,
        state=state,
        adapter_label=adapter_label,
    )


def _event_bus(runtime: _GovernedActRuntime) -> "_RuntimeEventBus":
    from noesis.interfaces.observability import RuntimeEventBus

    episode_ctx = EpisodeContext(
        run_dir=runtime.run_dir,
        episode_id=runtime.episode_id,
        seed=0,
        task="",
        tags={},
        adapter_label=runtime.adapter_label,
        started_at=runtime.started_at,
    )
    return RuntimeEventBus(
        context=episode_ctx,
        emitter=CognitiveEventEmitter(run_dir=runtime.run_dir),
        lineage=LineageTracker(),
        clock=runtime.clock,
        now=_now_dt(runtime),
        event_id_factory=runtime.event_id_factory,
    )


def _now_dt(runtime: _GovernedActRuntime) -> Callable[[], datetime]:
    if isinstance(runtime.clock, RuntimeClock):
        return lambda: datetime.now(timezone.utc)
    return lambda: runtime.clock.now()  # type: ignore[return-value]


def _state_hash(run_dir: Path) -> str:
    return compute_sha256(run_dir / "state.json")


def _build_candidate(
    *,
    kind: str,
    payload: Mapping[str, Any],
    provenance: Mapping[str, Any] | None,
    risk_tags: Sequence[str] | None,
    redaction: Mapping[str, Any] | None,
    state_hash: str,
) -> ActionCandidate:
    redaction_spec = _parse_redaction(redaction)
    return ActionCandidate(
        id=None,
        kind=kind,
        payload=dict(payload),
        state_ref="state.json",
        state_hash=state_hash,
        redaction=redaction_spec,
        provenance=dict(provenance) if provenance else None,
        risk_tags=tuple(risk_tags or ()),
    )


def _parse_redaction(redaction: Mapping[str, Any] | None) -> RedactionSpec:
    if redaction is None:
        return _DEFAULT_REDACTION
    return RedactionSpec(
        mode=str(redaction.get("mode", _DEFAULT_REDACTION.mode)),
        policy_id=str(redaction.get("policy_id", _DEFAULT_REDACTION.policy_id)),
        policy_version=str(redaction.get("policy_version", _DEFAULT_REDACTION.policy_version)),
        field_rules=dict(redaction.get("field_rules") or {}),
    )


def _resolve_adapter_label(kind: str, payload: Mapping[str, Any]) -> str:
    adapter_label = payload.get("adapter_label")
    if isinstance(adapter_label, str) and adapter_label:
        return adapter_label
    return f"adapter:{kind}"


def _resolve_tool_label(kind: str, payload: Mapping[str, Any], adapter_label: str) -> str:
    tool = payload.get("tool")
    if isinstance(tool, str) and tool:
        return tool
    return adapter_label or kind


def _input_excerpt(goal: str, payload: Mapping[str, Any]) -> str:
    if "command" in payload:
        return str(payload.get("command", ""))[:120]
    if "input_excerpt" in payload:
        return str(payload.get("input_excerpt", ""))[:120]
    if "cmd" in payload:
        return str(payload.get("cmd", ""))[:120]
    return str(goal)[:120]


def _resolve_policy(mode: GovernanceMode, override: PreActGovernor | None) -> PreActGovernor | None:
    if mode is GovernanceMode.OFF:
        return None
    return override or PreActGovernor()


def _resolve_executor(kind: str, registry: Any) -> Callable[..., Any]:
    if kind == "shell":
        if registry.shell_executor is None:
            raise ValueError("shell executor is not configured; call ns.set(shell_executor=...)")
        return registry.shell_executor
    if kind == "adapter":
        if registry.adapter_executor is None:
            raise ValueError("adapter executor is not configured; call ns.set(adapter_executor=...)")
        return registry.adapter_executor
    raise ValueError(f"unsupported action kind: {kind!r}")


def _invoke_executor(executor: Callable[..., Any], payload: Mapping[str, Any]) -> Any:
    try:
        return executor(**dict(payload))
    except TypeError:
        return executor(payload)


def _governance_message(gate: Any) -> str:
    if gate.governance_result and gate.governance_result.message:
        return gate.governance_result.message
    return "Action blocked by governance"


def _veto_exception(gate: Any, kind: str) -> NoesisVeto:
    result = gate.governance_result
    message = result.message if result else "Action vetoed"
    return NoesisVeto(
        advice=message,
        target=kind,
        scope="governance.pre_act",
        decision=str(result.decision.value) if result else None,
        rule_id=result.rule_id if result else None,
        policy_id=result.policy_id if result else None,
        policy_version=result.policy_version if result else None,
        policy_kind=result.policy_kind if result else None,
        enforced=bool(result.enforced) if result else None,
        details=result.details if result else None,
        error=result.error if result else None,
        governance_id=str(result.governance_id) if result else None,
        action_candidate_id=gate.candidate.id if gate.candidate else None,
    )


def _message_for_status(goal: str, outcome: str, error: Exception | None) -> str:
    if outcome == "ok":
        return f"Completed action for: {goal}"
    return str(error) if error else "Action failed"


def _adapter_result(status: str) -> str:
    if status == "ok":
        return "success"
    if status == "vetoed":
        return "skipped"
    return "error"


def _outcome_for_status(status: str) -> str:
    if status == "ok":
        return "success_unverified"
    return "error"


def _default_verification() -> dict[str, object | None]:
    return VerificationSummary(
        provided=False,
        passed=None,
        assertions=(),
        workspace_diff=None,
        snapshots=None,
        policy=SnapshotPolicy(ignore=DEFAULT_IGNORE, symlinks="skip"),
        error=None,
    ).to_dict()


def _finalize_terminal(
    *,
    runtime: _GovernedActRuntime,
    context: RuntimeContext,
    status: str,
    message: str,
) -> None:
    runtime.state.set_outcome(status=status, summary=message, metrics={"success": 1.0 if status == "ok" else 0.0})
    runtime.state_repo.persist(runtime.state)
    _terminate_event(
        runtime.run_dir,
        runtime.episode_id,
        {"status": status, "message": message},
        now_fn=runtime.now_fn,
        id_factory=runtime.event_id_factory,
    )
    _finalize_summary(
        run_dir=runtime.run_dir,
        episode_id=runtime.episode_id,
        task=runtime.state.task,
        seed=runtime.state.seed,
        started_at=runtime.started_at,
        intuition_enabled=False,
        intuition_mode=runtime.state.intuition_mode,
        using_label=runtime.adapter_label,
        tags=runtime.state.tags,
        intuition=None,
        process_id=runtime.state.process_id,
        process_name=runtime.state.process_name,
        process_kind=runtime.state.process_kind,
        process_run_index=runtime.state.process_run_index,
        schema_version=SUMMARY_SCHEMA_VERSION,
        config=_config_snapshot(context),
        ports=context.list_ports(),
        adapter_result=_adapter_result(status),
        outcome=_outcome_for_status(status),
        verification=_default_verification(),
    )
    ensure_learn_file(runtime.run_dir)
    persist_episode_memory(run_dir=runtime.run_dir, context=context)
    _finalize_manifest(runtime.run_dir, runtime.episode_id)


def _finalize_manifest(run_dir: Path, episode_id: str) -> None:
    writer = ManifestWriter(run_dir=run_dir, episode_id=episode_id)
    writer.finalize()
    _ = compute_sha256(writer.manifest_path)


def _begin_episode(runs_dir: Path, episode_id: str) -> Path:
    from noesis.state.episode import begin_episode

    return begin_episode(str(runs_dir), episode_id)


def _mint_episode_ids(seed: int, determinism: "DeterminismConfig | None") -> EpisodeIds:
    if determinism:
        reset_ulid_state()
        return EpisodeIds.mint(
            seed=seed,
            timestamp_ms=determinism.episode_timestamp_ms,
            entropy=determinism.rng.bytes(10),
        )
    return EpisodeIds.mint(seed=seed)


def _init_clock(
    determinism: "DeterminismConfig | None",
) -> tuple[RuntimeClock, Callable[[], str]]:
    if determinism:
        from noesis.runtime.determinism import DeterministicClock

        run_clock = DeterministicClock(
            start_at=determinism.clock.start_at,
            tick_ms=determinism.clock.tick_ms,
        )
        return run_clock, lambda: run_clock.now().isoformat()
    clock = RuntimeClock()
    return clock, lambda: datetime.now(timezone.utc).isoformat()


__all__ = ["DefaultActuationPort", "governed_act_impl"]
