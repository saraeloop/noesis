from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest

from noesis.domain.faculties.intuition import IntuitionMode
from noesis.domain.learning.model import LearnMode
from noesis.context import RuntimeContext
from noesis.interfaces.config import ConfigPort, ConfigSnapshot, PlannerMode
from noesis.runtime.session import (
    DefaultSessionProvider,
    NoesisSession,
    RunnerProtocol,
    SessionBuilder,
)
from noesis.runtime.session.runner_port import SessionRunRequest


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


def _snapshot_for(tmp_path: Path, *, planner: PlannerMode = PlannerMode.MINIMAL) -> ConfigSnapshot:
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
    }
    return ConfigSnapshot.from_mapping(payload)


def _session(tmp_path: Path) -> NoesisSession:
    snapshot = _snapshot_for(tmp_path)
    builder = SessionBuilder(config_port=_FakeConfigPort(snapshot))
    return builder.build()


def test_session_run_produces_artifacts(tmp_path: Path) -> None:
    session = _session(tmp_path)
    episode_id = session.run("Summarize repository status", intuition=False)
    assert episode_id.startswith("ep_")
    assert (tmp_path / episode_id / "summary.json").exists()


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
