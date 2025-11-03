from __future__ import annotations

from noesis.domain.faculties.intuition import HeuristicIntuition, LLMIntuition


def test_heuristic_intuition_intervention() -> None:
    policy = HeuristicIntuition()
    event = policy.advise({"task": "demo", "normalize": False})
    assert event is not None
    assert event.kind == "intervention"
    assert event.patch == {"normalize": True}


def test_heuristic_intuition_hint_for_length() -> None:
    policy = HeuristicIntuition(max_task_length=10)
    event = policy.advise({"task": "x" * 20})
    assert event is not None
    assert event.kind == "hint"


def test_llm_intuition_uses_provider() -> None:
    def _provider(state):
        return {"kind": "hint", "advice": "Mock response", "confidence": 0.8}

    policy = LLMIntuition(response_provider=_provider)
    event = policy.advise({"task": "demo"})
    assert event is not None
    assert event.advice == "Mock response"
