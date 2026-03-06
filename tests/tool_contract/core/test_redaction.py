from __future__ import annotations

from noesis.domain.tool_contract import (
    PayloadRedactionPolicy,
    REDACTED_VALUE,
    apply_redaction,
    build_payload_evidence,
)


def test_redaction_policy_redacts_and_hashes_target_fields() -> None:
    policy = PayloadRedactionPolicy(
        redact_fields=("token",),
        hash_fields=("body",),
    )
    payload = {
        "path": "README.md",
        "token": "secret",
        "body": "sensitive-content",
    }

    redacted = apply_redaction(payload, policy)

    assert redacted["path"] == "README.md"
    assert redacted["token"] == REDACTED_VALUE
    assert str(redacted["body"]).startswith("sha256:")


def test_build_payload_evidence_marks_redaction_state() -> None:
    payload = {"path": "README.md", "token": "secret"}
    evidence = build_payload_evidence(
        payload,
        PayloadRedactionPolicy(redact_fields=("token",)),
    )

    assert evidence.redaction_applied is True
    assert evidence.redacted_payload["token"] == REDACTED_VALUE
    assert evidence.normalized_payload == payload
    assert evidence.request_fingerprint.startswith("sha256:")
