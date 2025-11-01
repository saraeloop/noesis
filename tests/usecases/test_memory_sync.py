from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Sequence

import pytest

from noesis.interfaces.config import ConfigPort, ConfigSnapshot
from noesis.interfaces.memory import Fact, MemoryPort, MemoryQuery
from noesis.runtime.config_provider import RuntimeContext
from noesis.usecases.memory_sync import LONG_TERM_CAPABILITY, persist_episode_memory
from noesis.trace.events import read_events


class DummyConfigPort(ConfigPort):
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


class InMemoryPort(MemoryPort):
    __api_version__ = "memory/1.1"

    def __init__(self) -> None:
        self.facts: Dict[str, Fact] = {}
        self.links: Dict[str, Sequence[str]] = {}

    def supports(self, capability: str) -> bool:
        return capability == LONG_TERM_CAPABILITY

    def write_fact(self, fact: Fact) -> None:
        self.facts[fact.id] = fact

    def query(self, query: MemoryQuery, *, k: int = 5):
        return list(self.facts.values())[:k]

    def link_episode(self, episode_id: str, fact_ids: Sequence[str]) -> None:
        self.links[episode_id] = list(fact_ids)


@pytest.fixture(name="runtime_context")
def _runtime_context(tmp_path: Path) -> RuntimeContext:
    snapshot = ConfigSnapshot.from_mapping(
        {
            "runs_dir": str(tmp_path),
            "agents": "agents.yaml",
            "tasks": "tasks.yaml",
            "timeout_sec": 60,
            "intuition_mode": "advisory",
            "direction_min_confidence": 0.5,
            "policy_aliases": {},
            "learn_mode": "off",
            "learn_home": str(tmp_path / "learn"),
            "learn_auto_apply_min_successes": 1,
            "learn_auto_apply_min_confidence": 0.8,
        }
    )
    context = RuntimeContext(config_port=DummyConfigPort(snapshot))
    memory_port = InMemoryPort()
    context.register("memory", memory_port, api=memory_port.__api_version__)
    return context


def _write_summary(run_dir: Path, payload: Dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(json.dumps(payload), encoding="utf-8")


def test_persist_episode_memory_writes_fact_and_event(tmp_path: Path, runtime_context: RuntimeContext):
    run_dir = tmp_path / "ep"
    summary_payload: Dict[str, Any] = {
        "episode_id": "ep_test",
        "task": "Summarize findings",
        "started_at": "2025-10-31T12:00:00Z",
        "duration_sec": 42.5,
        "flags": {"intuition": True},
        "tags": {"priority": "high"},
        "metrics": {"success": 0.9},
        "ports": {"memory": "memory/1.1"},
    }
    _write_summary(run_dir, summary_payload)

    persist_episode_memory(run_dir=run_dir, context=runtime_context)

    memory_port: InMemoryPort = runtime_context.resolve("memory")  # type: ignore[assignment]
    assert "episode:ep_test" in memory_port.facts
    fact = memory_port.facts["episode:ep_test"]
    assert fact.metadata["episode_id"] == "ep_test"
    assert fact.metadata["metrics"]["success"] == 0.9
    assert memory_port.links["ep_test"] == ["episode:ep_test"]

    events = read_events(run_dir)
    memory_events = [event for event in events if event.get("phase") == "memory"]
    assert memory_events
    assert memory_events[-1]["payload"]["status"] == "persisted"
