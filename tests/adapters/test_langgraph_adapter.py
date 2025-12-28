from __future__ import annotations

from typing import Any, Dict

from noesis.adapters.langgraph import LangGraphAdapter


def test_langgraph_adapter_invokes_graph() -> None:
    class DummyGraph:
        def invoke(self, payload: Any) -> Dict[str, Any]:
            return {"result": payload}

    adapter = LangGraphAdapter(DummyGraph())
    assert adapter.invoke("demo") == {"result": "demo"}
    assert adapter.execute(task="demo", episode_id="ep", run_dir="runs") == {"result": "demo"}


def test_langgraph_adapter_respects_input_mapper() -> None:
    class DummyGraph:
        def invoke(self, payload: Any) -> Dict[str, Any]:
            return payload

    adapter = LangGraphAdapter(DummyGraph(), input_mapper=lambda t: {"task": t, "meta": "ok"})
    assert adapter.invoke("demo") == {"task": "demo", "meta": "ok"}


def test_langgraph_adapter_handles_async() -> None:
    class AsyncGraph:
        async def invoke(self, payload: Any) -> str:
            return payload + " async"

    adapter = LangGraphAdapter(AsyncGraph())
    assert adapter.invoke("hello") == "hello async"
