from __future__ import annotations

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
