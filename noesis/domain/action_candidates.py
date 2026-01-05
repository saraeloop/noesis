"""
Domain model for action candidates.

Action candidates describe pending side-effectful operations in a deterministic,
schema-governed form. They are pure data carriers and contain no I/O logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence
import json


ACTION_CANDIDATE_SCHEMA_VERSION = "action_candidate/1.0.0"


def _canonical_dumps(value: Any) -> str:
    """Serialize JSON with stable ordering for deterministic hashing."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


@dataclass(frozen=True, slots=True)
class RedactionSpec:
    """Explicit redaction policy metadata for sensitive fields."""

    mode: str
    policy_id: str
    policy_version: str
    field_rules: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "field_rules": dict(self.field_rules),
        }


@dataclass(frozen=True, slots=True)
class ActionCandidate:
    """Canonical description of a pending side effect."""

    id: str | None
    kind: str
    payload: Mapping[str, Any]
    state_ref: str
    state_hash: str
    redaction: RedactionSpec
    provenance: Mapping[str, Any] | None = None
    risk_tags: Sequence[str] = ()
    schema_version: str = ACTION_CANDIDATE_SCHEMA_VERSION

    def with_id(self, candidate_id: str) -> "ActionCandidate":
        """Return a copy with a deterministic identifier assigned."""
        return replace(self, id=candidate_id)

    def to_mapping(self) -> dict[str, Any]:
        """Render a JSON-serializable candidate payload."""
        return self._to_mapping(require_id=True)

    def _to_mapping(self, *, require_id: bool) -> dict[str, Any]:
        if require_id and not self.id:
            raise ValueError("ActionCandidate.id must be set before emission")
        payload: dict[str, Any] = {
            "schema_version": self.schema_version,
            "action_candidate_id": self.id,
            "kind": self.kind,
            "payload": dict(self.payload),
            "state_ref": self.state_ref,
            "state_hash": self.state_hash,
            "redaction": self.redaction.to_dict(),
        }
        if self.provenance:
            payload["provenance"] = dict(self.provenance)
        if self.risk_tags:
            payload["risk_tags"] = list(self.risk_tags)
        return payload

    def canonical_payload(self) -> dict[str, Any]:
        """Return the canonical payload used for deterministic IDs."""
        payload = self._to_mapping(require_id=False)
        payload.pop("action_candidate_id", None)
        return payload

    def canonical_json(self) -> str:
        """Return a canonical JSON string for hashing."""
        return _canonical_dumps(self.canonical_payload())


__all__ = ["ActionCandidate", "RedactionSpec", "ACTION_CANDIDATE_SCHEMA_VERSION"]
