# tests/test_direction.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

import pytest

import noesis as ns
from noesis import DirectedIntuition, NoesisVeto


# Minimal graph doubles

class DictGraph:
    def __init__(self) -> None:
        # Mapper lets Noēsis treat string tasks as dict inputs (so patches can apply)
        self.__noesis_input_mapper__ = lambda task: {
            "task": task,
            "normalize": False,
            "risk": "medium",
        }

    def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # Echo back so we can observe post-patch state in summary/events if needed
        return payload


class StringGraph:
    def invoke(self, text: str) -> str:
        return text.upper()


# Policies under test

class AppliedPolicy(DirectedIntuition):
    def advise(self, state):
        return self.intervene(
            advice="Normalize before processing",
            patch={"normalize": True},
            confidence=0.9,
        )


class EmptyPatchPolicy(DirectedIntuition):
    def advise(self, state):
        return self.intervene(advice="No-op", patch={})


class LowConfidencePolicy(DirectedIntuition):
    def advise(self, state):
        return self.intervene(
            advice="Unsure",
            patch={"normalize": True},
            confidence=0.3,
        )


class MultiPatchPolicy(DirectedIntuition):
    def advise(self, state):
        return self.intervene(
            advice="Tune inputs",
            patch={"normalize": True, "risk": "low"},
            confidence=0.9,
        )


class VetoPolicy(DirectedIntuition):
    def advise(self, state):
        return self.veto(advice="Unsafe task")


class RewritePolicy(DirectedIntuition):
    def advise(self, state):
        text = state["task"]
        return self.intervene(
            advice="Rewrite input",
            patch={"rewrite": f"{text} LIMIT 5"},
            confidence=0.9,
        )


# Helpers

@dataclass
class RunArtifacts:
    episode_id: str
    summary: Dict[str, Any]
    direction_payloads: List[Dict[str, Any]]
    events: List[Dict[str, Any]]


def _run(tmpdir, *, graph, policy, min_confidence: float = 0.5) -> RunArtifacts:
    runs_dir = tmpdir / "runs"
    ns.set(runs_dir=str(runs_dir), direction_min_confidence=min_confidence)
    ep = ns.solve("Demo task", using=lambda: graph, intuition=policy)
    summ = ns.summary(ep)
    evs = ns.events(ep)
    payloads = [e["payload"] for e in evs if e.get("phase") == "direction"]
    return RunArtifacts(ep, summ, payloads, evs)


# ----- Tests: direction reasons + diffs + metrics -----------------------------

def test_direction_applied(tmp_path):
    art = _run(tmp_path, graph=DictGraph(), policy=AppliedPolicy())
    payload = art.direction_payloads[-1]

    assert payload["reason"] == "applied"
    assert payload["applied"] is True
    assert payload["diff"] == [{"key": "normalize", "before": False, "after": True}]

    # flags expose threshold for dashboards
    assert art.summary["flags"]["direction"]["threshold"] == pytest.approx(0.5)

    # metrics roll-up
    mets = art.summary["metrics"]
    assert mets.get("direction_events", 0) >= 1
    assert mets.get("direction_applied", 0) >= 1
    assert mets.get("direction_vetoed", 0) == 0
    assert mets.get("act_count") == mets.get("steps")
    assert mets.get("interpret_count") >= 1

    # both intuition and direction events exist
    phases = {e.get("phase") for e in art.events}
    assert "intuition" in phases
    assert "direction" in phases


def test_direction_empty_patch(tmp_path):
    art = _run(tmp_path, graph=DictGraph(), policy=EmptyPatchPolicy())
    payload = art.direction_payloads[-1]
    assert payload["reason"] == "empty_patch"
    assert payload["applied"] is False
    assert payload.get("diff", []) == []


def test_direction_low_confidence(tmp_path):
    art = _run(
        tmp_path,
        graph=DictGraph(),
        policy=LowConfidencePolicy(),
        min_confidence=0.8,  # above policy's 0.3
    )
    payload = art.direction_payloads[-1]
    assert payload["reason"] == "policy_low_confidence"
    assert payload["applied"] is False
    assert payload.get("diff", []) == []


def test_direction_not_dict_input(tmp_path):
    art = _run(tmp_path, graph=StringGraph(), policy=AppliedPolicy())
    payload = art.direction_payloads[-1]
    assert payload["reason"] == "not_patchable_input"
    assert payload["applied"] is False
    assert payload.get("diff", []) == []


def test_direction_rewrite_patch(tmp_path):
    art = _run(tmp_path, graph=StringGraph(), policy=RewritePolicy())
    payload = art.direction_payloads[-1]
    assert payload["reason"] == "rewritten"
    assert payload["applied"] is True
    assert payload.get("diff", []) == [{"key": "rewrite", "before": "Demo task", "after": "Demo task LIMIT 5"}]


def test_direction_multi_patch_diff(tmp_path):
    art = _run(tmp_path, graph=DictGraph(), policy=MultiPatchPolicy())
    payload = art.direction_payloads[-1]
    # order should reflect shallow-merge order; assert by keys
    diff_keys = [d["key"] for d in payload["diff"]]
    assert diff_keys == ["normalize", "risk"]


def test_direction_veto(tmp_path):
    runs_dir = tmp_path / "runs"
    ns.set(runs_dir=str(runs_dir), direction_min_confidence=0.5)

    with pytest.raises(NoesisVeto):
        ns.solve("Danger", using=lambda: DictGraph(), intuition=VetoPolicy())

    # Fetch the most recent episode recorded in this isolated runs_dir
    runs = ns.list_runs(limit=1)
    assert runs, "expected a recorded episode after veto"
    ep = runs[0]["episode_id"]
    summ = ns.summary(ep)
    assert summ["flags"]["direction"]["vetoed"] == 1

    payloads = [e["payload"] for e in ns.events(ep) if e.get("phase") == "direction"]
    assert payloads[-1]["reason"] == "veto"


def test_learn_event_emitted(tmp_path):
    art = _run(tmp_path, graph=DictGraph(), policy=AppliedPolicy())
    learn_events = [e for e in art.events if e.get("phase") == "learn"]
    assert learn_events, "expected learn event in episode"
    payload = learn_events[-1]["payload"]
    assert payload.get("policy_id")
    assert payload.get("applied") is False
    assert payload.get("approval") in {"pending", "approved", "auto-applied"}
    assert payload.get("id", "").endswith(f":{art.episode_id}")
    assert isinstance(payload.get("proposal"), list)
    for proposal in payload.get("proposal", []):
        assert {"proposal_id", "kind", "target", "status"}.issubset(proposal.keys())
