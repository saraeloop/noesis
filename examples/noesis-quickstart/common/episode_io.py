from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Tuple

from noesis.runtime.paths import resolve_noesis_paths, find_episode_dir


def episode_dir(runs_dir: str | Path, episode_id: str) -> Path:
    runs_path = Path(runs_dir)
    layout = resolve_noesis_paths(workspace=None, runs_dir=runs_path)
    found = find_episode_dir(episode_id, layout)
    if found is not None:
        return found
    return layout.episodes_dir / episode_id


def episode_dir_from_runs_dir(runs_dir: str | Path, episode_id: str) -> Path:
    return episode_dir(runs_dir, episode_id)


def read_events_jsonl(runs_dir: str | Path, episode_id: str, limit: int = 50) -> list[dict[str, Any]]:
    ep = episode_dir(runs_dir, episode_id)
    path = ep / "events.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"events.jsonl not found: {path}")

    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                events.append(obj)
        except Exception:
            continue
        if len(events) >= limit:
            break
    return events


def read_summary_json(runs_dir: str | Path, episode_id: str) -> dict[str, Any]:
    ep = episode_dir(runs_dir, episode_id)
    path = ep / "summary.json"
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def read_events(ns: Any, ep_dir: Path | str, episode_id: str, limit: int = 50) -> list[dict[str, Any]]:
    # `ns` is unused on purpose; keep signature stable for tutorials.
    path = Path(ep_dir) / "events.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"events.jsonl not found: {path}")

    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                events.append(obj)
        except Exception:
            continue
        if len(events) >= limit:
            break
    return events


def read_summary(ep_dir: Path | str) -> dict[str, Any]:
    path = Path(ep_dir) / "summary.json"
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def read_state(ep_dir: Path | str) -> dict[str, Any]:
    path = Path(ep_dir) / "state.json"
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def summarize_timeline(events: Iterable[dict[str, Any]], limit: int = 20) -> list[Tuple[str, str]]:
    lines: list[Tuple[str, str]] = []
    for e in list(events)[:limit]:
        verb = e.get("phase") or e.get("verb") or e.get("kind") or "event"
        payload = e.get("payload") if isinstance(e.get("payload"), dict) else {}
        status = (
            payload.get("status")
            or payload.get("outcome")
            or payload.get("message")
            or payload.get("tool")
            or "ok"
        )
        lines.append((str(verb), str(status)))
    return lines
