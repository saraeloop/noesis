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

from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import json

from . import config as _cfg
from .state.episode import EpisodeSummary, new_episode_id, begin_episode
from .trace.events import read_events, write_event
from .trace.summary import write_summary
from .intuition import Intuition, IntuitionEvent, NullIntuition, IntuitionMode
from .exceptions import NoesisVeto
from .loader import load_graph, GraphSource
from .insight import compute_metrics

# Soft-depend on adapters
try:
    from .adapters.langgraph import LangGraphAdapter  # type: ignore
except Exception:  # noqa: BLE001
    LangGraphAdapter = None  # type: ignore[assignment]

SCHEMA_VERSION = "1.0.0"


# shared helpers (module scope) 

def _fmt_value(val: Any) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if val is None:
        return "null"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, str):
        return repr(val)
    return json.dumps(val)


def _format_diff_item(item: Dict[str, Any]) -> str:
    before = _fmt_value(item.get("before"))
    after = _fmt_value(item.get("after"))
    return f"{item.get('key')}: {before}→{after}"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso8601(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def _compute_duration(events: list[Dict[str, Any]]) -> float:
    start_at: datetime | None = None
    end_at: datetime | None = None
    for evt in events:
        ts = evt.get("timestamp")
        if not isinstance(ts, str):
            continue
        parsed = _parse_iso8601(ts)
        if parsed is None:
            continue
        if start_at is None and evt.get("phase") == "start":
            start_at = parsed
        if evt.get("phase") in {"terminate", "error"}:
            end_at = parsed
    if start_at and end_at and end_at >= start_at:
        return (end_at - start_at).total_seconds()
    return 0.0


def _normalize_intuition(intuition: bool | Intuition | None) -> tuple[Intuition, bool]:
    """
    Respect global string config for intuition mode. Users set it via:
        ns.set(intuition_mode="advisory" | "interventive" | "hybrid")
    """
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
    return intuition, True


def _start_event(run_dir: Path, episode_id: str, payload: Dict[str, Any]) -> None:
    write_event(
        run_dir,
        {
            "timestamp": _now(),
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "start",
            "payload": payload,
            "evidence_ids": [],
        },
    )


def _observe_event(run_dir: Path, episode_id: str, payload: Dict[str, Any]) -> None:
    write_event(
        run_dir,
        {
            "timestamp": _now(),
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "observe",
            "payload": payload,
            "evidence_ids": [],
        },
    )


def _terminate_event(run_dir: Path, episode_id: str, payload: Dict[str, Any]) -> None:
    write_event(
        run_dir,
        {
            "timestamp": _now(),
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "terminate",
            "payload": payload,
            "evidence_ids": [],
        },
    )


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
            "evidence_ids": evt.evidence_ids,
        },
    )


def _safe_using_label(using: GraphSource) -> str:
    if isinstance(using, str):
        return using
    if callable(using):
        return getattr(using, "__name__", "callable")
    return using.__class__.__name__


def _load_graph(source: GraphSource) -> Any:
    return load_graph(source)


def _select_adapter(graph_obj: Any, min_confidence: float):
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
            if hasattr(self.obj, "run"):
                return self.obj.run(task)
            if callable(self.obj):
                return self.obj(task)
            raise TypeError("object is neither runnable nor callable")

    return _CallableAdapter(graph_obj)


def _finalize_summary(
    *,
    run_dir: Path,
    episode_id: str,
    task: str,
    seed: int,
    started_at: str,
    intuition_enabled: bool,
    intuition_mode: IntuitionMode,
    using_label: Optional[str],
    tags: Optional[Dict[str, Any]],
) -> None:
    ev = read_events(run_dir)
    duration_sec = _compute_duration(ev)

    flags: Dict[str, Any] = {
        "intuition": intuition_enabled,
        "mode": intuition_mode.value if intuition_enabled else "off",
    }
    if using_label is not None:
        flags["using"] = using_label

    summ = EpisodeSummary(
        schema_version=SCHEMA_VERSION,
        episode_id=episode_id,
        task=task,
        seed=seed,
        started_at=started_at,
        duration_sec=duration_sec,
        flags=flags,
        agents_config_hash="sha256:TODO",
        answer={},
        metrics=compute_metrics({}, ev),
        tags=tags or {},
    ).__dict__

    metrics_bucket = summ.setdefault("metrics", {})
    metrics_bucket["intuition_events"] = sum(1 for e in ev if e.get("phase") == "intuition")

    direction_events = [e for e in ev if e.get("phase") == "direction"]
    metrics_bucket["direction_events"] = len(direction_events)
    metrics_bucket["direction_applied"] = sum(
        1
        for e in direction_events
        if e.get("payload", {}).get("applied") and e.get("payload", {}).get("status") != "blocked"
    )
    metrics_bucket["direction_vetoed"] = sum(
        1 for e in direction_events if e.get("payload", {}).get("status") == "blocked"
    )

    last_payload = direction_events[-1].get("payload", {}) if direction_events else {}
    diff_strings = []
    for d in last_payload.get("diff", []) or []:
        try:
            diff_strings.append(_format_diff_item(d))
        except Exception:
            continue

    write_event(
        run_dir,
        {
            "timestamp": _now(),
            "episode_id": episode_id,
            "agent_id": "system",
            "phase": "insight",
            "payload": summ.get("metrics", {}),
            "evidence_ids": [],
        },
    )

    direction_flags = {
        "applied": metrics_bucket["direction_applied"],
        "vetoed": metrics_bucket["direction_vetoed"],
        "last_diff": diff_strings,
        "threshold": _cfg.get()["direction_min_confidence"],
    }
    policy_tag = last_payload.get("policy")
    if policy_tag:
        direction_flags["policy"] = policy_tag
    summ.setdefault("flags", {})["direction"] = direction_flags
    write_summary(run_dir, summ)


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
    run_dir = begin_episode(cfg["runs_dir"], episode_id)
    started_at = _now()

    intuition_impl, intuition_enabled = _normalize_intuition(intuition)

    _start_event(run_dir, episode_id, {"task": task, "seed": seed})
    _maybe_intuition(
        run_dir,
        episode_id,
        intuition_enabled,
        intuition_impl,
        {"task": task, "seed": seed, "history": [], "tools_seen": [], "tags": tags or {}},
    )
    _terminate_event(run_dir, episode_id, {"status": "noop"})

    _finalize_summary(
        run_dir=run_dir,
        episode_id=episode_id,
        task=task,
        seed=seed,
        started_at=started_at,
        intuition_enabled=intuition_enabled,
        intuition_mode=getattr(intuition_impl, "mode", IntuitionMode.ADVISORY),
        using_label=None,
        tags=tags,
    )
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
    run_dir = begin_episode(cfg["runs_dir"], episode_id)
    started_at = _now()

    intuition_impl, intuition_enabled = _normalize_intuition(intuition)

    _start_event(
        run_dir,
        episode_id,
        {"task": task, "seed": seed, "using": _safe_using_label(using)},
    )
    _maybe_intuition(
        run_dir,
        episode_id,
        intuition_enabled,
        intuition_impl,
        {"task": task, "seed": seed, "history": [], "tools_seen": [], "tags": tags or {}},
    )

    graph = _load_graph(using)
    adapter = _select_adapter(graph, _cfg.get()["direction_min_confidence"])

    veto_error: NoesisVeto | None = None

    try:
        result = adapter.execute(
            task=task,
            episode_id=episode_id,
            run_dir=run_dir,
            intuition=intuition_impl if intuition_enabled else None,
            seed=seed,
            tags=tags,
        )

        # Only core-log for the simple callable shim; real adapters log themselves.
        if type(adapter).__name__ == "_CallableAdapter":
            _observe_event(run_dir, episode_id, {"result_excerpt": str(result)[:400]})
            _terminate_event(run_dir, episode_id, {"status": "ok"})

    except NoesisVeto as e:
        _terminate_event(run_dir, episode_id, {"status": "blocked", "message": str(e)})
        veto_error = e
    except Exception as e:  # noqa: BLE001
        _terminate_event(run_dir, episode_id, {"status": "error", "message": str(e)})

    _finalize_summary(
        run_dir=run_dir,
        episode_id=episode_id,
        task=task,
        seed=seed,
        started_at=started_at,
        intuition_enabled=intuition_enabled,
        intuition_mode=getattr(intuition_impl, "mode", IntuitionMode.ADVISORY),
        using_label=_safe_using_label(using),
        tags=tags,
    )

    if veto_error is not None:
        raise veto_error
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
