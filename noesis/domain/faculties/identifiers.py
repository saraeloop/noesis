"""Stable identifier utilities for faculty artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

__all__ = [
    "DirectiveIdentifier",
    "GovernanceIdentifier",
    "make_directive_identifier",
    "make_governance_identifier",
]


@dataclass(frozen=True, slots=True)
class DirectiveIdentifier:
    """Stable identifier string for planner directives."""

    value: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


@dataclass(frozen=True, slots=True)
class GovernanceIdentifier:
    """Stable identifier string for governance decisions."""

    value: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


def make_directive_identifier(
    *,
    policy_id: str,
    policy_version: str,
    policy_kind: str,
    steps: Sequence[str],
    status: str,
    reason: str,
    applied: bool,
    diff: Sequence[Mapping[str, object]],
) -> DirectiveIdentifier:
    """Derive a deterministic identifier for a planner directive."""
    payload = {
        "policy_id": policy_id,
        "policy_version": policy_version,
        "policy_kind": policy_kind,
        "steps": list(steps),
        "status": status,
        "reason": reason,
        "applied": applied,
        "diff": [_canonicalize_mapping(item) for item in diff],
    }
    token = _stable_token(_canonical_json(payload))
    return DirectiveIdentifier(f"dir-{token}")


def make_governance_identifier(
    *,
    policy_id: str,
    policy_version: str,
    policy_kind: str,
    decision: str,
    rule_id: str,
    score: float,
    message: str,
    details: Mapping[str, object] | None,
) -> GovernanceIdentifier:
    """Derive a deterministic identifier for a governance result."""
    payload = {
        "policy_id": policy_id,
        "policy_version": policy_version,
        "policy_kind": policy_kind,
        "decision": decision,
        "rule_id": rule_id,
        "score": f"{score:.6f}",
        "message": message,
        "details": _canonicalize_mapping(details) if details else None,
    }
    token = _stable_token(_canonical_json(payload))
    return GovernanceIdentifier(f"gov-{token}")


def _stable_token(serialized: str) -> str:
    digest = hashlib.blake2b(serialized.encode("utf-8"), digest_size=12)
    return digest.hexdigest()


def _canonical_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _canonicalize_mapping(mapping: Mapping[str, object]) -> Mapping[str, object]:
    sanitized: dict[str, object] = {}
    for key in sorted(mapping):
        value = mapping[key]
        sanitized[key] = _sanitize_value(value)
    return sanitized


def _sanitize_value(value: object) -> object:
    if isinstance(value, Mapping):
        return _canonicalize_mapping(value)
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, float):
        return f"{value:.6f}"
    if isinstance(value, (int, bool)) or value is None:
        return value
    return str(value)

