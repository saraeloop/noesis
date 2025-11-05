from __future__ import annotations

import pytest

from noesis.domain.faculties import (
    FACULTY_HOOK_ORDER,
    GovernanceResult,
    InsightMetrics,
    IntuitionEvent,
    PlannerDirective,
    validate_hook_sequence,
    warn_on_incompatibility,
)
from noesis.domain.faculties.versioning import current_version, is_compatible


def test_schema_versions_match_registry() -> None:
    assert IntuitionEvent.schema_version == current_version("intuition")
    assert PlannerDirective.schema_version == current_version("direction")
    assert GovernanceResult.schema_version == current_version("governance")
    assert InsightMetrics.schema_version == current_version("insight")


def test_semver_compatibility_rules() -> None:
    assert is_compatible("1.0.0", "1.2.3")
    assert is_compatible("1.1.0", "1.2.0")
    assert not is_compatible("2.0.0", "1.0.0")
    assert not is_compatible("1.3.0", "1.2.0")


def test_round_trip_serialization() -> None:
    intuition_payload = {
        "schema_version": current_version("intuition"),
        "kind": "hint",
        "advice": "Check summary",
        "confidence": 0.55,
        "policy_id": "demo-policy",
        "policy_version": "1.0.0",
        "policy_kind": "rules",
        "applied": False,
        "rationale": None,
        "evidence_ids": [],
        "target": "input",
        "scope": "episode",
        "blocking": False,
    }
    intuition_event = IntuitionEvent.from_dict(intuition_payload)
    assert intuition_event.to_dict() == intuition_payload

    directive_payload = {
        "schema_version": current_version("direction"),
        "steps": ["alpha", "beta"],
        "status": "applied",
        "reason": "test",
        "diff": [{"key": "plan.steps[0]", "before": "a", "after": "b"}],
        "applied": True,
        "policy_id": "planner",
        "policy_version": "1.2.0",
        "policy_kind": "rules",
    }
    directive = PlannerDirective.from_mapping(directive_payload)
    expected = dict(directive_payload)
    expected["directive_id"] = str(directive.directive_id)
    expected["legacy_directive_id"] = str(directive.legacy_directive_id)
    assert directive.to_mapping() == expected

    governance_payload = {
        "schema_version": current_version("governance"),
        "decision": "audit",
        "rule_id": "rule",
        "score": 0.4,
        "message": "check",
        "policy_id": "gov",
        "policy_version": "1.0.0",
        "policy_kind": "rules",
        "details": {"foo": "bar"},
    }
    governance = GovernanceResult.from_mapping(governance_payload)
    expected_governance = dict(governance_payload)
    expected_governance["decision_id"] = str(governance.decision_id)
    expected_governance["governance_id"] = str(governance.governance_id)
    assert governance.to_mapping() == expected_governance

    insight_payload = {
        "schema_version": current_version("insight"),
        "phase_ms": {"act": 100},
        "veto_count": 0,
        "branching_factor": 0.0,
        "plan_adherence": 1.0,
        "success": True,
        "plan_revisions": 0,
        "tool_coverage": 1.0,
    }
    insight = InsightMetrics.from_mapping(insight_payload)
    assert insight.to_mapping() == insight_payload


def test_validate_hook_sequence() -> None:
    validate_hook_sequence(FACULTY_HOOK_ORDER)
    with pytest.raises(ValueError):
        validate_hook_sequence(["interpret", "observe"])
    with pytest.raises(ValueError):
        validate_hook_sequence(["observe", "act", "governance.pre_act"])


def test_warn_on_incompatibility() -> None:
    assert warn_on_incompatibility("intuition", "1.0.0")
    with pytest.warns(UserWarning):
        assert not warn_on_incompatibility("intuition", "2.0.0")
