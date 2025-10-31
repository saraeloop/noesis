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
from typing import Any, Dict, Optional, List, Final, Protocol

from . import _config as _cfg
from .state import (
    NoesisState,
    PlanStep,
    PLAN_KINDS_DEFAULT,
    PLAN_STATUS_DONE,
    OUTCOME_STATUS_OK,
    OUTCOME_STATUS_ERROR,
    OUTCOME_STATUS_VETOED,
    OUTCOME_STATUS_ABORTED,
    OUTCOME_STATUS_PARTIAL,
)
from .state.episode import new_episode_id, begin_episode
from .state.store import EpisodeStore
from .trace.events import write_event
from .intuition import Intuition, IntuitionEvent, NullIntuition, IntuitionMode
from .exceptions import NoesisVeto
from .loader import load_graph, GraphSource
from .runtime._utils import now as _now
from .runtime._events import (
    act_event as _act_event,
    ensure_act_event as _ensure_act_event,
    interpret_event as _interpret_event,
    observe_event as _observe_event,
    plan_event as _plan_event,
    reflect_event as _reflect_event,
    start_event as _start_event,
    terminate_event as _terminate_event,
)
from .runtime._summary import finalize_summary as _finalize_summary
from .trace.schema import SUMMARY_SCHEMA_VERSION

# Soft-depend on adapters
try:
    from .adapters.langgraph import LangGraphAdapter  # type: ignore
except Exception:  # noqa: BLE001
    LangGraphAdapter = None  # type: ignore[assignment]

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
                kind=PLAN_KINDS_DEFAULT,
                description=label.strip(),
            )
        )
    return steps


def _normalize_intuition(intuition: bool | Intuition | None) -> tuple[Intuition, bool]:
    """Normalize intuition argument without mutating caller-supplied policies."""
    mode_str = _cfg.get()["intuition_mode"]  # string
    mode = IntuitionMode(mode_str)           # Enum (internal only)

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
) -> IntuitionEvent | None:
    if not enabled:
        return None
    evt: IntuitionEvent | None = intuition.advise(snapshot)
    if not evt:
        return None
    write_event(
        run_dir,
        {
            "timestamp": _now(),
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
    # Wrap LangGraph-like objects that use .invoke OR .run
    if LangGraphAdapter is not None and (hasattr(graph_obj, "invoke") or hasattr(graph_obj, "run")):
        return LangGraphAdapter(graph_obj, min_confidence=min_confidence)

    class _CallableAdapter:
        def __init__(self, obj: Any):
            self.obj = obj

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
            if hasattr(self.obj, "invoke"):
                return self.obj.invoke(task)
            if hasattr(self.obj, "run"):
                return self.obj.run(task)
            if callable(self.obj):
                return self.obj(task)
            raise TypeError("object is neither runnable nor callable")

    return _CallableAdapter(graph_obj)


# Public API 

def set(**overrides: Any) -> None:
    _cfg.set(**overrides)


def solve(
    task: str,
    *,
    using: GraphSource,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
) -> str:
    return run_using(using=using, task=task, seed=seed, intuition=intuition, tags=tags)


@dataclass(slots=True)
class _EpCtx:
    episode_id: str
    run_dir: Path
    started_at: str


def _run_impl(
    *,
    task: str,
    seed: int,
    intuition: bool | Intuition,
    tags: Optional[Dict[str, Any]],
    using: Optional[GraphSource],
) -> str:
    cfg = _cfg.get()
    runs_dir = cfg["runs_dir"]
    dir_min = cfg["direction_min_confidence"]

    episode_id = new_episode_id(seed)
    run_dir = begin_episode(runs_dir, episode_id)
    ctx = _EpCtx(episode_id=episode_id, run_dir=run_dir, started_at=_now())

    intuition_impl, intuition_enabled = _normalize_intuition(intuition)

    raw_using_label: Optional[str] = _safe_using_label(using) if using is not None else None
    adapter_label = f"adapter:{raw_using_label or 'core.null'}"
    state = NoesisState.new(
        episode_id=ctx.episode_id,
        seed=seed,
        task=task,
        started_at=ctx.started_at,
        tags=tags,
        using=adapter_label,
    )
    state_path = ctx.run_dir / "state.json"
    state.write(state_path)

    snapshot = {
        "task": task,
        "seed": seed,
        "history": [],
        "tools_seen": [],
        "tags": tags or {},
        "state_path": str(state_path),
        "state": state.to_dict(),
    }
    if raw_using_label is not None:
        snapshot["using"] = raw_using_label

    start_payload = {"task": task, "seed": seed}
    if raw_using_label is not None:
        start_payload["using"] = raw_using_label

    _start_event(ctx.run_dir, ctx.episode_id, start_payload)
    _observe_event(ctx.run_dir, ctx.episode_id, task=task, tags=tags, snapshot=snapshot)
    _maybe_intuition(ctx.run_dir, ctx.episode_id, intuition_enabled, intuition_impl, snapshot)

    if raw_using_label is None:
        plan_steps = ["emit-summary-only"]
        plan_rationale = "Core run without adapter"
    else:
        plan_steps = [adapter_label]
        plan_rationale = "Execute adapter"
    plan_step_objs = _plan_steps_from_labels(plan_steps)
    state.set_plan(steps=plan_step_objs, rationale=plan_rationale, source="system")
    state.write(state_path)
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

    _reflect_event(ctx.run_dir, ctx.episode_id, success=success, reasons=reflect_reasons or None)
    _terminate_event(ctx.run_dir, ctx.episode_id, status_payload)

    if state.plan.steps:
        if not success and status_payload["status"] == "blocked":
            state.plan.steps[-1].status = "vetoed"
        elif not success:
            state.plan.steps[-1].status = "failed"
        else:
            state.plan.steps[-1].status = PLAN_STATUS_DONE

    normalized_outcome_status = _normalize_outcome_status(status_payload["status"], success=success)
    state.set_outcome(status=normalized_outcome_status, summary=result_excerpt or None)
    state.write(state_path)
    snapshot["state"] = state.to_dict()

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
    )

    try:
        store_root = Path(runs_dir) / "_episodes"
        summary_path = ctx.run_dir / "summary.json"
        EpisodeStore(store_root, ttl_days=EPISODE_STORE_TTL_DAYS).append(
            episode_id=ctx.episode_id,
            summary_path=summary_path,
            state_path=state_path,
            status=status_payload["status"],
            task=task,
            using=adapter_label,
            provenance={
                "schema_version": state.version,
                "state_schema_version": state.state_schema_version,
            },
        )
    except Exception:
        # Episode registry should never break execution; failures are logged via events.
        pass

    state.set_links(
        events="events.jsonl",
        summary="summary.json",
        learn="learn.jsonl",
    )
    state.write(state_path)

    if veto_error is not None:
        raise veto_error
    return ctx.episode_id


def run(
    task: str,
    *,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
) -> str:
    return _run_impl(task=task, seed=seed, intuition=intuition, tags=tags, using=None)


def run_using(
    *,
    using: GraphSource,
    task: str,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
) -> str:
    return _run_impl(task=task, seed=seed, intuition=intuition, tags=tags, using=using)


def run_graph(
    kind: GraphSource,
    *,
    task: str,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
) -> str:
    return run_using(using=kind, task=task, seed=seed, intuition=intuition, tags=tags)
