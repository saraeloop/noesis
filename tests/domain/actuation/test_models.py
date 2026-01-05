from __future__ import annotations

from noesis.domain.actuation.models import ActuationResult, ActuationStatus


def test_actuation_result_to_mapping_includes_populated_fields() -> None:
    result = ActuationResult(
        status=ActuationStatus.BLOCKED,
        summary="blocked by policy",
        error={"type": "policy"},
        artifacts=({"type": "log", "uri": "logs/act.txt"},),
        duration_ms=12,
        metadata={"policy_id": "rules.v1"},
        reasons=["rules.veto.danger"],
        metrics={"success": 0.0},
    )

    payload = result.to_mapping()

    assert payload["status"] == "blocked"
    assert payload["summary"] == "blocked by policy"
    assert payload["error"] == {"type": "policy"}
    assert payload["artifacts"] == [{"type": "log", "uri": "logs/act.txt"}]
    assert payload["duration_ms"] == 12
    assert payload["metadata"] == {"policy_id": "rules.v1"}
    assert payload["reasons"] == ["rules.veto.danger"]
    assert payload["metrics"] == {"success": 0.0}
