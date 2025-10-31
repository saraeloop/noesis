from __future__ import annotations

import noesis as ns
from examples.incident_triage import ProdGuardPolicy, incident_graph


def test_incident_graph_returns_expected_keys():
    result = incident_graph(
        "Scale checkout pods in us-west",
        tags={"env": "prod"},
    )
    assert result["severity"] in {"high", "medium", "critical"}
    assert isinstance(result["signals"], list)
    assert isinstance(result["actions"], list)
    assert result["notes"]


def test_incident_graph_requires_approval_when_tagged():
    result = incident_graph(
        "Rollback checkout-service to previous stable version",
        tags={"require_approval": True},
    )
    action = result["actions"][-1]
    assert action["status"] == "blocked_pending_approval"
    assert result["approvals"][-1]["status"] == "awaiting_approval"
    assert any("human_ok" in note for note in result["notes"])


def test_prod_guard_policy_vetoes_high_risk_tag():
    policy = ProdGuardPolicy()
    event = policy.advise({"task": "Investigate db leak", "tags": {"risk": "high"}})
    assert event is not None
    assert event.kind == "veto"
