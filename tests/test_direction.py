from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import noesis as ns
from noesis.direction import DirectedIntuition
from noesis.intuition import RiskLevel, ScrutinyLevel, StrategyHint, ToolConstraint


class DictGraph:
    def __init__(self) -> None:
        self.__noesis_input_mapper__ = lambda task: {"task": task, "normalize": False}

    def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return payload


class SignalPolicy(DirectedIntuition):
    def advise(self, state):
        return self.hint(
            advice="Consider safety bounds.",
            risk_level=RiskLevel.HIGH,
            strategy_hints=(StrategyHint.RETRIEVE_MORE, StrategyHint.VERIFY_FIRST),
            tool_constraints=(ToolConstraint.READ_ONLY,),
            scrutiny_level=ScrutinyLevel.STRICT,
            evidence_ids=["event:observe:1"],
        )


class VetoSignalPolicy(DirectedIntuition):
    def advise(self, state):
        return self.veto(advice="Unsafe task.")


@dataclass
class RunArtifacts:
    summary: Dict[str, Any]
    events: List[Dict[str, Any]]


def _run(tmpdir, *, policy) -> RunArtifacts:
    runs_dir = tmpdir / "runs"
    learn_dir = tmpdir / "learn"
    original = ns.get()
    try:
        ns.set(
            runs_dir=str(runs_dir),
            learn_home=str(learn_dir),
            planner_mode="meta",
            governance_mode="off",
        )
        ep = ns.solve("Demo task", using=lambda: DictGraph(), intuition=policy)
        summ = ns.summary.read(ep)
        evs = list(ns.events.read(ep))
        return RunArtifacts(summ, evs)
    finally:
        ns.set(**original)


def test_intuition_emits_signals_and_direction_applies_meta_plan(tmp_path):
    art = _run(tmp_path, policy=SignalPolicy())
    phases = {e.get("phase") for e in art.events}
    assert "intuition" in phases
    assert "direction" in phases

    direction_events = [e for e in art.events if e.get("phase") == "direction"]
    payload = direction_events[-1]["payload"]
    assert payload["status"] in {"applied", "skipped"}
    assert payload["intuition_event_id"]
    assert payload["risk_level"] == "high"
    assert payload["strategy_hints"] == ["retrieve_more", "verify_first"]
    assert payload["tool_constraints"] == ["read_only"]
    assert payload["scrutiny_level"] == "strict"
    assert direction_events[-1]["evidence_ids"] == ["event:observe:1"]
    if payload["status"] == "applied":
        diff_keys = [item.get("key") for item in payload.get("diff", [])]
        assert any(
            key and key in {"plan.steps[0].description", "plan.steps[1].description", "plan.steps[2].description"}
            for key in diff_keys
        )


def test_intuition_veto_does_not_block_act_without_governance(tmp_path):
    art = _run(tmp_path, policy=VetoSignalPolicy())
    act_events = [e for e in art.events if e.get("phase") == "act"]
    assert act_events, "intuition veto should not block act without governance"
