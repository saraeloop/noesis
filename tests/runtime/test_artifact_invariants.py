import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.util import find_spec
from pathlib import Path

import pytest
from jsonschema import validate

import noesis as ns
from noesis.cli.viewer import load_episode_view
from noesis.cli.view_models import build_episode_dashboard
from noesis.runtime.artifacts.manifest import compute_sha256
from noesis.runtime.normalization import normalize_using
from noesis.trace.schema import events_schema_path


def _load_schema(name: str, version: str) -> dict:
    if name == "event":
        path = Path(events_schema_path(version))
    else:
        path = Path(__file__).resolve().parents[2] / "docs" / "schema" / name / f"{version}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@contextmanager
def _tutorial_context(tmp_path: Path) -> Path:
    tutorial_root = Path(__file__).resolve().parents[2] / "examples" / "noesis-quickstart"
    runs_dir = tmp_path / "runs"
    learn_dir = tmp_path / "learn"
    runs_dir.mkdir(parents=True, exist_ok=True)
    learn_dir.mkdir(parents=True, exist_ok=True)

    original_cwd = Path.cwd()
    original_env = dict(os.environ)
    sys.path.insert(0, str(tutorial_root))
    os.environ["NOESIS_RUNS_DIR"] = str(runs_dir)
    os.environ["NOESIS_LEARN_HOME"] = str(learn_dir)
    os.chdir(tmp_path)
    try:
        yield runs_dir
    finally:
        os.chdir(original_cwd)
        os.environ.clear()
        os.environ.update(original_env)
        if sys.path and sys.path[0] == str(tutorial_root):
            sys.path.pop(0)


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _read_events(run_dir: Path) -> list[dict]:
    events_path = run_dir / "events.jsonl"
    return [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _validate_manifest(run_dir: Path) -> dict:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    schema = _load_schema("manifest", "1.0.0")
    validate(instance=manifest, schema=schema)
    for item in manifest.get("files", []):
        path = run_dir / item["name"]
        assert path.exists(), f"manifest listed missing file: {path}"
        assert item["size_bytes"] == path.stat().st_size
        assert item["sha256"] == compute_sha256(path)
    return manifest


def _validate_events(run_dir: Path) -> list[dict]:
    schema = _load_schema("event", "1.2.0")
    events = _read_events(run_dir)
    for event in events:
        validate(instance=event, schema=schema)
    return events


def _validate_summary(run_dir: Path) -> dict:
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    schema = _load_schema("summary", "1.3.0")
    validate(instance=summary, schema=schema)
    return summary


def _validate_learn(run_dir: Path) -> list[dict]:
    learn_path = run_dir / "learn.jsonl"
    if not learn_path.exists():
        return []
    schema = _load_schema("learn", "1.0.0")
    records = [
        json.loads(line)
        for line in learn_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for record in records:
        validate(instance=record, schema=schema)
    return records


def _assert_monotonic_timestamps(events: list[dict]) -> None:
    last: datetime | None = None
    for event in events:
        ts = event.get("timestamp")
        if not isinstance(ts, str):
            continue
        current = _parse_ts(ts)
        if last is not None:
            assert current >= last, "event timestamps are not monotonic"
        last = current


def _act_count(events: list[dict]) -> int:
    count = 0
    for event in events:
        if event.get("phase") != "act":
            continue
        payload = event.get("payload")
        if isinstance(payload, dict) and payload.get("synthetic"):
            continue
        count += 1
    return count


def _validate_cross_links(run_dir: Path, events: list[dict], summary: dict, manifest: dict) -> None:
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    normalized = normalize_using(state.get("episode", {}).get("using"))
    expected_using = normalized.display if normalized else state.get("episode", {}).get("using")

    assert summary["flags"]["using"] == expected_using

    start_events = [event for event in events if event.get("phase") == "start"]
    if start_events:
        start_using = (start_events[-1].get("payload") or {}).get("using")
        assert start_using == expected_using

    learn_records = _validate_learn(run_dir)
    learn_ids = {record.get("id") for record in learn_records if record.get("id")}
    learn_event_paths = [
        event.get("payload", {}).get("learn_path")
        for event in events
        if event.get("phase") == "learn"
    ]
    if any(path == "learn.jsonl" for path in learn_event_paths):
        learn_path = run_dir / "learn.jsonl"
        assert learn_path.exists()
        assert state.get("links", {}).get("learn") == "learn.jsonl"
        manifest_files = manifest.get("files", [])
        assert any(
            item.get("kind") == "learn" and item.get("name") == "learn.jsonl"
            for item in manifest_files
        )

    for event in events:
        if event.get("phase") != "learn":
            continue
        payload = event.get("payload") or {}
        assert payload.get("learn_path") == "learn.jsonl"
        assert payload.get("learn_schema") == "learn/1.0"
        assert isinstance(payload.get("proposal_count"), int)
        proposal_ids = payload.get("proposal_ids") or []
        assert all(pid in learn_ids for pid in proposal_ids)
        assert isinstance(proposal_ids, list)


def _validate_insight_consistency(events: list[dict], summary: dict) -> None:
    expected = {
        "plan_adherence": summary["metrics"].get("plan_adherence"),
        "tool_coverage": summary["metrics"].get("tool_coverage"),
        "veto_count": summary["metrics"].get("veto_count"),
        "success": summary["metrics"].get("success"),
        "act_count": summary["metrics"].get("act_count"),
    }
    insight_events = [event for event in events if event.get("phase") == "insight"]
    if not insight_events:
        return
    payload = insight_events[-1].get("payload") or {}
    metrics = payload.get("metrics") or {}
    assert metrics == expected


def _validate_run(run_dir: Path) -> None:
    events = _validate_events(run_dir)
    summary = _validate_summary(run_dir)
    manifest = _validate_manifest(run_dir)

    _assert_monotonic_timestamps(events)
    assert summary["metrics"].get("act_count") == _act_count(events)
    _validate_cross_links(run_dir, events, summary, manifest)
    _validate_insight_consistency(events, summary)


def test_artifact_invariants_hello_and_veto(tmp_path: Path) -> None:
    with _tutorial_context(tmp_path) as runs_dir:
        from tutorials import hello_episode

        assert hello_episode.main() == 0
        episodes = [
            p for p in runs_dir.iterdir() if p.is_dir() and p.name not in {"_episodes", "processes"}
        ]
        assert episodes, "hello_episode did not emit an episode"
        latest_run = max(episodes, key=lambda p: p.stat().st_mtime)
        _validate_run(latest_run)
        view = load_episode_view(
            str(latest_run),
            ns=ns,
            runtime_context=None,
        )
        assert not view.validation, "noesis view reported validation issues"
        dashboard = build_episode_dashboard(latest_run, validate=True)
        assert not dashboard.validation_issues, "noesis view dashboard reported validation issues"

    if find_spec("langgraph") is None or find_spec("openai") is None:
        pytest.skip("guarded_langgraph dependencies missing")
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set for guarded_langgraph tutorial")

    with _tutorial_context(tmp_path / "guarded") as runs_dir:
        from tutorials import guarded_langgraph

        assert guarded_langgraph.main() == 0
        episodes = [p for p in runs_dir.iterdir() if p.is_dir() and p.name != "_episodes"]
        assert episodes, "guarded_langgraph did not emit episodes"
        veto_runs = []
        for episode_dir in episodes:
            summary_path = episode_dir / "summary.json"
            if not summary_path.exists():
                continue
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if summary.get("status") == "vetoed":
                veto_runs.append(episode_dir)
        assert veto_runs, "guarded_langgraph did not emit a vetoed episode"
        _validate_run(veto_runs[-1])
