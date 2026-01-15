from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pytest

import noesis as ns
from noesis.domain.faculties.intuition import IntuitionMode
from noesis.domain.learning.model import LearnMode
from noesis.context import RuntimeContext
from noesis.interfaces.config import ConfigPort, ConfigSnapshot, PlannerMode
from noesis.runtime.paths import resolve_noesis_paths
from noesis.runtime.session import (
    DefaultSessionProvider,
    NoesisSession,
    RunnerProtocol,
    SessionBuilder,
)
from noesis.runtime.session.runner_port import SessionRunRequest
from noesis.runtime.determinism import DeterministicClock, DeterministicRNG


class _FakeConfigPort(ConfigPort):
    __api_version__ = "config/1.0-rc1"

    def __init__(self, snapshot: ConfigSnapshot) -> None:
        self._snapshot = snapshot

    def get(self) -> ConfigSnapshot:
        return self._snapshot

    def set(self, **overrides: object) -> ConfigSnapshot:
        data = self._snapshot.to_mapping()
        data.update(overrides)
        self._snapshot = ConfigSnapshot.from_mapping(data)
        return self._snapshot

    def reload(self) -> ConfigSnapshot:
        return self._snapshot

    def supports(self, capability: str) -> bool:
        return False


class _RecordingRunner(RunnerProtocol):
    def __init__(self) -> None:
        self.requests: list[SessionRunRequest] = []

    def run(self, request: SessionRunRequest, *, context: RuntimeContext) -> str:
        self.requests.append(request)
        return "ep_runner_custom"


def _snapshot_for(
    tmp_path: Path,
    *,
    planner: PlannerMode = PlannerMode.MINIMAL,
    prompt_enabled: bool = False,
    prompt_mode: str = "hash_only",
) -> ConfigSnapshot:
    learn_home = tmp_path / "learn"
    learn_home.mkdir(parents=True, exist_ok=True)
    payload: Mapping[str, object] = {
        "runs_dir": str(tmp_path),
        "agents": "agents.toml",
        "tasks": "tasks.toml",
        "timeout_sec": 5,
        "intuition_mode": IntuitionMode.ADVISORY.value,
        "direction_min_confidence": 0.5,
        "planner_mode": planner.value,
        "policy_aliases": {},
        "learn_mode": LearnMode.OFF.value,
        "learn_home": str(learn_home),
        "learn_auto_apply_min_successes": 1,
        "learn_auto_apply_min_confidence": 0.5,
        "prompt_provenance_enabled": prompt_enabled,
        "prompt_provenance_mode": prompt_mode,
    }
    return ConfigSnapshot.from_mapping(payload)


def _session(tmp_path: Path) -> NoesisSession:
    snapshot = _snapshot_for(tmp_path)
    builder = SessionBuilder(config_port=_FakeConfigPort(snapshot))
    return builder.build()


def _episode_dir(tmp_path: Path, episode_id: str) -> Path:
    layout = resolve_noesis_paths(workspace=None, runs_dir=tmp_path)
    return layout.episodes_dir / episode_id


def test_session_run_produces_artifacts(tmp_path: Path) -> None:
    session = _session(tmp_path)
    episode_id = session.run("Summarize repository status", intuition=False)
    assert episode_id.startswith("ep_")
    assert (_episode_dir(tmp_path, episode_id) / "summary.json").exists()


def test_session_runner_protocol_invoked(tmp_path: Path) -> None:
    session = _session(tmp_path)
    runner = _RecordingRunner()
    episode_id = session.run("Custom run", runner=runner)
    assert episode_id == "ep_runner_custom"
    assert len(runner.requests) == 1
    assert runner.requests[0].task == "Custom run"


def test_default_session_provider_scoped_override(tmp_path: Path) -> None:
    provider = DefaultSessionProvider()
    baseline = provider.current()
    custom_session = _session(tmp_path)
    with provider.use(custom_session):
        assert provider.current() is custom_session
    assert provider.current() is baseline


def test_ns_run_respects_session_override(tmp_path: Path) -> None:
    provider = ns.session_provider()
    custom_session = _session(tmp_path)
    with provider.use(custom_session):
        episode_id = ns.run("Ensure override works", intuition=False)
    assert (_episode_dir(tmp_path, episode_id) / "summary.json").exists()


def test_prompt_provenance_manifest_listing(tmp_path: Path) -> None:
    snapshot = _snapshot_for(tmp_path, prompt_enabled=True, prompt_mode="full")
    session = SessionBuilder(config_port=_FakeConfigPort(snapshot)).build()

    episode_id = session.run("Capture prompt provenance", intuition=False)
    run_dir = _episode_dir(tmp_path, episode_id)
    prompt_path = run_dir / "prompts.jsonl"

    assert prompt_path.exists(), "prompts.jsonl should be created when provenance is enabled"
    lines = prompt_path.read_text(encoding="utf-8").splitlines()
    assert lines, "prompts.jsonl should contain at least one entry"
    records = [json.loads(line) for line in lines]
    phases = {rec["phase"] for rec in records}
    agent_ids = {rec["agent_id"] for rec in records}
    assert episode_id == records[0]["episode_id"]
    assert "plan" in phases
    assert "interpret" in phases or "reflect" in phases
    assert "direction.planner" in agent_ids
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    names = {entry["name"] for entry in manifest.get("files", [])}
    assert "prompts.jsonl" in names


def test_prompt_provenance_join_sanity(tmp_path: Path) -> None:
    snapshot = _snapshot_for(tmp_path, prompt_enabled=True, prompt_mode="hash_only")
    session = SessionBuilder(config_port=_FakeConfigPort(snapshot)).build()

    episode_id = session.run("Join sanity", intuition=False)
    run_dir = _episode_dir(tmp_path, episode_id)
    prompt_path = run_dir / "prompts.jsonl"
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    lines = prompt_path.read_text(encoding="utf-8").splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    assert all(rec["episode_id"] == episode_id for rec in records)
    assert summary["episode_id"] == episode_id
    phases = {rec["phase"] for rec in records}
    assert len(phases) >= 2, "should capture multiple phases for join sanity"


def test_session_allows_parallel_runs(tmp_path: Path) -> None:
    snapshot = _snapshot_for(tmp_path, prompt_enabled=False)
    session = SessionBuilder(config_port=_FakeConfigPort(snapshot)).build()

    def _run_task(name: str) -> str:
        return session.run(name, intuition=False)

    from concurrent.futures import ThreadPoolExecutor

    tasks = ["parallel-1", "parallel-2"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_run_task, tasks))

    assert len(set(results)) == 2
    for episode_id in results:
        assert (_episode_dir(tmp_path, episode_id) / "summary.json").exists()


def test_session_reuse_does_not_leak_state(tmp_path: Path) -> None:
    snapshot = _snapshot_for(tmp_path, prompt_enabled=False)
    session = SessionBuilder(config_port=_FakeConfigPort(snapshot)).build()

    first = session.run("first", intuition=False)
    second = session.run("second", intuition=False)

    assert first != second
    for episode_id, task in [(first, "first"), (second, "second")]:
        summary = json.loads((_episode_dir(tmp_path, episode_id) / "summary.json").read_text(encoding="utf-8"))
        assert summary["task"] == task


def test_session_configure_preserves_determinism(tmp_path: Path) -> None:
    snapshot = _snapshot_for(tmp_path)
    builder = SessionBuilder(config_port=_FakeConfigPort(snapshot))
    clock = DeterministicClock()
    rng = DeterministicRNG(seed=123)
    session = builder.with_determinism(clock=clock, rng=rng, episode_timestamp_ms=111).build()

    before = session.determinism
    assert before is not None

    session.configure(planner_mode=PlannerMode.MINIMAL.value)

    after = session.determinism
    assert after is before
