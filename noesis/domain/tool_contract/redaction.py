"""Redaction rules for payload evidence persisted by the tool contract."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Mapping

from .fingerprints import fingerprint_payload
from .models import PayloadEvidence

REDACTED_VALUE = "[REDACTED]"


@dataclass(frozen=True, slots=True)
class PayloadRedactionPolicy:
    """Field-level redaction policy for payload artifacts."""

    redact_fields: tuple[str, ...] = field(default_factory=tuple)
    hash_fields: tuple[str, ...] = field(default_factory=tuple)


def apply_redaction(
    payload: Mapping[str, Any],
    policy: PayloadRedactionPolicy,
) -> dict[str, Any]:
    """Apply deterministic redaction/hashing to a normalized payload."""

    redacted: dict[str, Any] = {}
    for key, value in payload.items():
        if key in policy.redact_fields:
            redacted[key] = REDACTED_VALUE
        elif key in policy.hash_fields:
            redacted[key] = _hash_value(value)
        else:
            redacted[key] = value
    return redacted


def build_payload_evidence(
    payload: Mapping[str, Any],
    policy: PayloadRedactionPolicy | None = None,
) -> PayloadEvidence:
    """Create persistable payload evidence from a normalized payload."""

    effective_policy = policy or PayloadRedactionPolicy()
    redacted = apply_redaction(payload, effective_policy)
    return PayloadEvidence(
        normalized_payload=dict(payload),
        redacted_payload=redacted,
        request_fingerprint=fingerprint_payload(payload),
        redaction_applied=bool(effective_policy.redact_fields or effective_policy.hash_fields),
    )


def _hash_value(value: Any) -> str:
    digest = hashlib.sha256(repr(value).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


__all__ = [
    "PayloadRedactionPolicy",
    "REDACTED_VALUE",
    "apply_redaction",
    "build_payload_evidence",
]
