from __future__ import annotations

from noesis.domain.faculties.intuition import (
    HeuristicIntuition,
    LLMIntuition,
    RiskLevel,
    SalienceSignal,
    ScrutinyLevel,
    StrategyHint,
    ToolConstraint,
    derive_intuition_assessment,
)


def test_heuristic_intuition_intervention() -> None:
    policy = HeuristicIntuition()
    event = policy.advise({"task": "demo", "normalize": False})
    assert event is not None
    assert event.kind == "intervention"
    assert event.patch == {"normalize": True}
    assessment = derive_intuition_assessment(event)
    assert assessment.risk_level is RiskLevel.MODERATE
    assert assessment.salience_signals == (SalienceSignal.NORMALIZATION_GAP,)
    assert assessment.strategy_hints == (StrategyHint.VERIFY_FIRST,)
    assert assessment.tool_constraints == (ToolConstraint.REQUIRE_DOUBLE_CHECK,)
    assert assessment.scrutiny_level is ScrutinyLevel.ELEVATED


def test_heuristic_intuition_hint_for_length() -> None:
    policy = HeuristicIntuition(max_task_length=10)
    event = policy.advise({"task": "x" * 20})
    assert event is not None
    assert event.kind == "hint"
    assessment = derive_intuition_assessment(event)
    assert assessment.salience_signals == (SalienceSignal.TASK_COMPLEXITY,)
    assert assessment.strategy_hints == (StrategyHint.RETRIEVE_MORE, StrategyHint.NARROW_SCOPE)


def test_llm_intuition_uses_provider() -> None:
    def _provider(state):
        return {
            "kind": "hint",
            "advice": "Mock response",
            "confidence": 0.8,
            "risk_level": "high",
            "strategy_hints": ["verify_first"],
            "scrutiny_level": "strict",
        }

    policy = LLMIntuition(response_provider=_provider)
    event = policy.advise({"task": "demo"})
    assert event is not None
    assert event.advice == "Mock response"
    assessment = derive_intuition_assessment(event)
    assert assessment.risk_level is RiskLevel.HIGH
    assert assessment.scrutiny_level is ScrutinyLevel.STRICT
