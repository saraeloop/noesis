"""
Execution core: solve, run, run_using, run_graph (compat), set
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union, Callable

from . import config as _cfg
from .state.episode import EpisodeSummary, new_episode_id
from .trace.files import read_events, write_event, write_summary
from .eval.metrics import compute_metrics
from .intuition.base import Intuition, IntuitionEvent, NullIntuition
from .loader import load_graph, GraphSource

# Soft-depend on adapters
try:
    from .adapters.langgraph import LangGraphAdapter  # type: ignore
except Exception:  # noqa: BLE001
    LangGraphAdapter = None  # type: ignore[assignment]

SCHEMA_VERSION = "1.0.0"


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


def run(
    task: str,
    *,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
) -> str:
    cfg = _cfg.get()
    episode_id = new_episode_id(seed)
    run_dir = Path(cfg["runs_dir"]) / episode_id
    started_at = _now()

    intuition_impl, intuition_enabled = _normalize_intuition(intuition)

    _start_event(run_dir, episode_id, {"task": task, "seed": seed})
    _maybe_intuition(run_dir, episode_id, intuition_enabled, intuition_impl, {
        "task": task, "seed": seed, "history": [], "tools_seen": [], "tags": tags or {},
    })
    _terminate_event(run_dir, episode_id, {"status": "noop"})

    ev = read_events(run_dir)
    summ = EpisodeSummary(
        schema_version=SCHEMA_VERSION,
        episode_id=episode_id,
        task=task,
        seed=seed,
        started_at=started_at,
        flags={"intuition": intuition_enabled},
        agents_config_hash="sha256:TODO",
        answer={},
        metrics=compute_metrics({}, ev),
        tags=tags or {},
    ).__dict__
    summ.setdefault("metrics", {})["intuition_events"] = sum(1 for e in ev if e.get("phase") == "intuition")
    write_summary(run_dir, summ)
    return episode_id


def run_using(
    *,
    using: GraphSource,
    task: str,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
) -> str:
    cfg = _cfg.get()
    episode_id = new_episode_id(seed)
    run_dir = Path(cfg["runs_dir"]) / episode_id
    started_at = _now()

    intuition_impl, intuition_enabled = _normalize_intuition(intuition)

    _start_event(run_dir, episode_id, {"task": task, "seed": seed, "using": _safe_using_label(using)})
    _maybe_intuition(run_dir, episode_id, intuition_enabled, intuition_impl, {
        "task": task, "seed": seed, "history": [], "tools_seen": [], "tags": tags or {},
    })

    graph = _load_graph(using)
    adapter = _select_adapter(graph)
    try:
        result = adapter.execute(
            task=task,
            episode_id=episode_id,
            run_dir=run_dir,
            intuition=intuition_impl if intuition_enabled else None,
            seed=seed,
            tags=tags,
        )
        _observe_event(run_dir, episode_id, {"result_excerpt": str(result)[:400]})
    except Exception as e:  # noqa: BLE001
        _terminate_event(run_dir, episode_id, {"status": "error", "message": str(e)})

    ev = read_events(run_dir)
    summ = EpisodeSummary(
        schema_version=SCHEMA_VERSION,
        episode_id=episode_id,
        task=task,
        seed=seed,
        started_at=started_at,
        flags={"intuition": intuition_enabled, "using": _safe_using_label(using)},
        agents_config_hash="sha256:TODO",
        answer={},
        metrics=compute_metrics({}, ev),
        tags=tags or {},
    ).__dict__
    summ.setdefault("metrics", {})["intuition_events"] = sum(1 for e in ev if e.get("phase") == "intuition")
    write_summary(run_dir, summ)
    return episode_id


def run_graph(
    kind: GraphSource,
    *,
    task: str,
    seed: int = 0,
    intuition: bool | Intuition = True,
    tags: Optional[Dict[str, Any]] = None,
) -> str:
    return run_using(using=kind, task=task, seed=seed, intuition=intuition, tags=tags)


# Helpers (private) 

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_intuition(intuition: bool | Intuition | None) -> tuple[Intuition, bool]:
    if intuition is True:
        return NullIntuition(), True
    if intuition is False or intuition is None:
        return NullIntuition(), False
    return intuition, True  # type: ignore[return-value]


def _start_event(run_dir: Path, episode_id: str, payload: Dict[str, Any]) -> None:
    write_event(run_dir, {
        "timestamp": _now(),
        "episode_id": episode_id,
        "agent_id": "system",
        "phase": "start",
        "payload": payload,
        "evidence_ids": [],
    })


def _observe_event(run_dir: Path, episode_id: str, payload: Dict[str, Any]) -> None:
    write_event(run_dir, {
        "timestamp": _now(),
        "episode_id": episode_id,
        "agent_id": "system",
        "phase": "observe",
        "payload": payload,
        "evidence_ids": [],
    })


def _terminate_event(run_dir: Path, episode_id: str, payload: Dict[str, Any]) -> None:
    write_event(run_dir, {
        "timestamp": _now(),
        "episode_id": episode_id,
        "agent_id": "system",
        "phase": "terminate",
        "payload": payload,
        "evidence_ids": [],
    })


def _maybe_intuition(
    run_dir: Path,
    episode_id: str,
    enabled: bool,
    intuition: Intuition,
    snapshot: Dict[str, Any],
) -> None:
    if not enabled:
        return
    evt: IntuitionEvent | None = intuition.advise(snapshot)
    if not evt:
        return
    write_event(run_dir, {
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
        },
        "evidence_ids": evt.evidence_ids,
    })


def _safe_using_label(using: GraphSource) -> str:
    if isinstance(using, str):
        return using
    if callable(using):
        return getattr(using, "__name__", "callable")
    return using.__class__.__name__


def _load_graph(source: GraphSource) -> Any:
    return load_graph(source)


def _select_adapter(graph_obj: Any):
    if LangGraphAdapter is not None and hasattr(graph_obj, "run"):
        return LangGraphAdapter(graph_obj)

    class _CallableAdapter:
        def __init__(self, obj: Any):
            self.obj = obj
        def execute(self, *, task: str, episode_id: str, run_dir, intuition: Optional[Intuition] = None,
                    seed: int = 0, tags: Optional[Dict[str, Any]] = None) -> Any:
            if hasattr(self.obj, "run"):
                return self.obj.run(task)
            if callable(self.obj):
                return self.obj(task)
            raise TypeError("object is neither runnable nor callable")

    return _CallableAdapter(graph_obj)