from typing import Any

class _FakeGraph:
    def run(self, task: str) -> Any:
        # minimal stand-in; swap with real LangGraph later
        return f"[react] handled: {task}"

def make():
    return _FakeGraph()