from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest

from noesis.adapters.langgraph import LangGraphAdapter
from noesis.adapters.protocols import DEFAULT_MIN_CONFIDENCE
from noesis.direction import DirectedIntuition
from noesis.exceptions import NoesisVeto
from noesis.intuition import IntuitionEvent, IntuitionMode
from noesis.trace.events import read_events


class _BaseIntuition(DirectedIntuition):
    mode: IntuitionMode = IntuitionMode.INTERVENTIVE

    def advise(self, state: Dict[str, Any]) -> IntuitionEvent | None:  # pragma: no cover - implemented in subclasses
        raise NotImplementedError


class _PatchIntuition(_BaseIntuition):
    def advise(self, state: Dict[str, Any]) -> IntuitionEvent:
        return self.intervene(
            advice="Add metadata",
            patch={"meta": "patched"},
            confidence=1.0,
        )


class _LowConfidenceIntuition(_BaseIntuition):
    def advise(self, state: Dict[str, Any]) -> IntuitionEvent:
        return self.intervene(
            advice="Too uncertain",
            patch={"meta": "ignored"},
            confidence=DEFAULT_MIN_CONFIDENCE - 0.2,
        )


class _VetoIntuition(_BaseIntuition):
    def advise(self, state: Dict[str, Any]) -> IntuitionEvent:
        return self.veto(advice="Unsafe task")


def _events_for(tmp_path: Path) -> list[Dict[str, Any]]:
    return read_events(tmp_path / "episode")


def test_langgraph_adapter_emits_canonical_phases(tmp_path: Path) -> None:
    class DummyGraph:
        def invoke(self, payload: Any) -> Dict[str, Any]:
            return {"result": "ok", "tool_calls": [{"name": "search"}]}

    adapter = LangGraphAdapter(DummyGraph(), input_mapper=lambda t: {"task": t})
    run_dir = tmp_path / "episode"
    result = adapter.execute(task="demo", episode_id="ep1", run_dir=run_dir)

    assert result["result"] == "ok"
    records = _events_for(tmp_path)
    phases = [record["phase"] for record in records]
    assert phases[:4] == ["observe", "interpret", "plan", "act"]
    assert phases[4] == "reflect"
    assert all("metrics" in record for record in records), "expected timing metrics on every event"
    assert all(record.get("caused_by") for record in records[1:]), "expected causal lineage after first event"
    act_payload = records[3]["payload"]
    assert act_payload["outcome"] == "ok"
    assert act_payload["tools"] == ["search"]


def test_langgraph_adapter_applies_direction_patch(tmp_path: Path) -> None:
    class DummyGraph:
        def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
            return payload

    adapter = LangGraphAdapter(DummyGraph(), input_mapper=lambda t: {"task": t})
    run_dir = tmp_path / "episode"
    result = adapter.execute(
        task="demo",
        episode_id="ep2",
        run_dir=run_dir,
        intuition=_PatchIntuition(),
    )

    assert result["meta"] == "patched"
    plan_record = next(
        record
        for record in _events_for(tmp_path)
        if record["phase"] == "plan" and "status" in record["payload"]
    )
    assert plan_record["payload"]["status"] == "applied"


def test_langgraph_adapter_skips_low_confidence_patch(tmp_path: Path) -> None:
    class DummyGraph:
        def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
            return payload

    adapter = LangGraphAdapter(DummyGraph())
    run_dir = tmp_path / "episode"
    result = adapter.execute(
        task="demo",
        episode_id="ep3",
        run_dir=run_dir,
        intuition=_LowConfidenceIntuition(),
    )

    assert result == "demo"
    plan_record = next(
        record
        for record in _events_for(tmp_path)
        if record["phase"] == "plan" and record["payload"].get("reason") == "policy_low_confidence"
    )
    assert plan_record["payload"]["status"] == "skipped"


def test_langgraph_adapter_veto(tmp_path: Path) -> None:
    class DummyGraph:
        def invoke(self, payload: Any) -> Dict[str, Any]:
            return payload

    adapter = LangGraphAdapter(DummyGraph())
    run_dir = tmp_path / "episode"
    with pytest.raises(NoesisVeto):
        adapter.execute(
            task="demo",
            episode_id="ep4",
            run_dir=run_dir,
            intuition=_VetoIntuition(),
        )

    plan_record = next(
        record
        for record in _events_for(tmp_path)
        if record["phase"] == "plan" and record["payload"].get("status") == "blocked"
    )
    assert plan_record["payload"]["reason"] == "veto"


def test_langgraph_adapter_handles_async(tmp_path: Path) -> None:
    class AsyncGraph:
        async def invoke(self, payload: Any) -> str:
            return payload + " async"

    adapter = LangGraphAdapter(AsyncGraph())
    run_dir = tmp_path / "episode"
    result = adapter.execute(task="hello", episode_id="ep5", run_dir=run_dir)
    assert result == "hello async"
