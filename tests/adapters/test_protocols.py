from __future__ import annotations

from noesis.adapters.crewai import CrewAIAdapter
from noesis.adapters.langgraph import LangGraphAdapter
from noesis.adapters.protocols import DEFAULT_MIN_CONFIDENCE, STATE_HISTORY_LIMIT


def test_protocol_constants():
    assert DEFAULT_MIN_CONFIDENCE == 0.5
    assert STATE_HISTORY_LIMIT == 50


def test_langgraph_adapter_executes(tmp_path):
    class DummyGraph:
        def invoke(self, payload):
            return payload

    adapter = LangGraphAdapter(DummyGraph())
    result = adapter.execute(
        task="run demo",
        episode_id="ep-adapter",
        run_dir=tmp_path / "episode",
        intuition=None,
    )

    assert result == "run demo"


def test_crewai_adapter_wraps_langgraph(tmp_path):
    class DummyCrew:
        def kickoff(self, payload):
            return {"status": "ok", **payload}

    adapter = CrewAIAdapter(DummyCrew())
    run_dir = tmp_path / "episode"
    output = adapter.execute(task="crew task", episode_id="ep-crew", run_dir=run_dir)

    assert output["task"] == "crew task"
