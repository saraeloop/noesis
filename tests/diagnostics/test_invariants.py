from __future__ import annotations

from noesis.diagnostics.invariants import check_action_candidate_invariants


def test_action_candidate_invariants_require_id_and_schema_version() -> None:
    events = [
        {
            "id": "evt-1",
            "phase": "action_candidate",
            "payload": {
                "schema_version": "action_candidate/0.9.0",
                "action_candidate_id": None,
                "state_hash": "sha256:BAD",
            },
        }
    ]

    violations = check_action_candidate_invariants(events)

    details = {violation.detail for violation in violations}
    assert "action_candidate missing action_candidate_id" in details
    assert "action_candidate schema_version mismatch" in details
    assert "action_candidate state_hash invalid" in details
