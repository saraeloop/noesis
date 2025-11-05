"""Directional directives and policy helpers for Noēsis."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Dict, Mapping, Optional, Sequence
from uuid import UUID, uuid4

from .intuition import Intuition, IntuitionEvent, IntuitionMode, PolicyKind, StateSnapshot
from .identifiers import DirectiveIdentifier, make_directive_identifier
from .versioning import current_version, is_compatible

__all__ = [
    "DirectiveKind",
    "DirectiveStatus",
    "DirectiveDiff",
    "PlannerDirective",
    "DirectedIntuition",
]


class DirectiveKind(str, Enum):
    HINT = "hint"
    INTERVENTION = "intervention"
    VETO = "veto"


class DirectiveStatus(str, Enum):
    """Outcome for a planner directive emitted by Direction."""

    APPLIED = "applied"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class DirectiveDiff:
    """Represents a single field-level mutation proposed by Direction."""

    key: str
    before: Any
    after: Any

    def to_mapping(self) -> Dict[str, Any]:
        return {"key": self.key, "before": self.before, "after": self.after}

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "DirectiveDiff":
        return cls(
            key=str(payload.get("key", "")),
            before=payload.get("before"),
            after=payload.get("after"),
        )


@dataclass(frozen=True, slots=True)
class PlannerDirective:
    """Versioned contract describing a directional plan mutation."""

    schema_version: ClassVar[str] = current_version("direction")
    steps: Sequence[str]
    status: DirectiveStatus
    reason: str
    diff: Sequence[DirectiveDiff] = ()
    applied: bool = False
    policy_id: str = "unspecified"
    policy_version: str = "0.0.0"
    policy_kind: PolicyKind = "rules"
    directive_id: DirectiveIdentifier | None = None
    legacy_directive_id: UUID = field(default_factory=uuid4)

    def to_mapping(self) -> Dict[str, Any]:
        """Render the directive into a JSON-serializable mapping."""
        return {
            "schema_version": self.schema_version,
            "steps": list(self.steps),
            "status": self.status.value,
            "reason": self.reason,
            "diff": [diff.to_mapping() for diff in self.diff],
            "applied": self.applied,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_kind": self.policy_kind,
            "directive_id": str(self.directive_id),
            "legacy_directive_id": str(self.legacy_directive_id),
        }

    def __post_init__(self) -> None:
        if self.policy_kind not in ("llm", "rules", "hybrid"):
            raise ValueError(f"Invalid policy_kind '{self.policy_kind}' for PlannerDirective")
        identifier = self.directive_id
        if isinstance(identifier, DirectiveIdentifier):
            computed = identifier
        elif isinstance(identifier, str) and _looks_like_stable_directive_id(identifier):
            computed = DirectiveIdentifier(identifier)
        else:
            computed = make_directive_identifier(
                policy_id=self.policy_id,
                policy_version=self.policy_version,
                policy_kind=self.policy_kind,
                steps=tuple(self.steps),
                status=self.status.value,
                reason=self.reason,
                applied=self.applied,
                diff=tuple(diff.to_mapping() for diff in self.diff),
            )
        object.__setattr__(self, "directive_id", computed)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "PlannerDirective":
        """Construct a directive from a JSON payload, ignoring unknown fields."""
        version = str(payload.get("schema_version", cls.schema_version))
        if not is_compatible(version, cls.schema_version):
            raise ValueError(
                f"Incompatible direction schema version '{version}' (expected ≤ {cls.schema_version})"
            )
        status_raw = payload.get("status", DirectiveStatus.SKIPPED.value)
        try:
            status = DirectiveStatus(status_raw)
        except ValueError:
            status = DirectiveStatus.SKIPPED
        directive_id_raw = payload.get("directive_id")
        legacy_id_raw = payload.get("legacy_directive_id") or payload.get("directive_uuid")
        legacy_uuid = _parse_uuid(legacy_id_raw)
        diff_payload = payload.get("diff")
        if not isinstance(diff_payload, (list, tuple)):
            diff_payload = []
        diff_items = [DirectiveDiff.from_mapping(item) for item in diff_payload]
        steps_payload = payload.get("steps", ())
        if not isinstance(steps_payload, (list, tuple)):
            steps_payload = ()
        steps_tuple = tuple(str(item) for item in steps_payload)
        policy_kind = payload.get("policy_kind", "rules")
        if policy_kind not in ("llm", "rules", "hybrid"):
            policy_kind = "rules"
        stable_identifier: DirectiveIdentifier | None = None
        if isinstance(directive_id_raw, str) and _looks_like_stable_directive_id(directive_id_raw):
            stable_identifier = DirectiveIdentifier(directive_id_raw)
        else:
            if legacy_uuid is None and isinstance(directive_id_raw, str):
                legacy_uuid = _parse_uuid(directive_id_raw)
            stable_identifier = make_directive_identifier(
                policy_id=str(payload.get("policy_id", "unspecified")),
                policy_version=str(payload.get("policy_version", "0.0.0")),
                policy_kind=policy_kind,
                steps=steps_tuple,
                status=status.value,
                reason=str(payload.get("reason", "")),
                applied=bool(payload.get("applied", False)),
                diff=tuple(diff.to_mapping() for diff in diff_items),
            )
        if legacy_uuid is None:
            legacy_uuid = uuid4()
        return cls(
            steps=steps_tuple,
            status=status,
            reason=payload.get("reason", ""),
            diff=tuple(diff_items),
            applied=bool(payload.get("applied", False)),
            policy_id=str(payload.get("policy_id", "unspecified")),
            policy_version=str(payload.get("policy_version", "0.0.0")),
            policy_kind=policy_kind,  # type: ignore[arg-type]
            directive_id=stable_identifier,
            legacy_directive_id=legacy_uuid,
        )


class DirectedIntuition(Intuition):
    mode: IntuitionMode = IntuitionMode.ADVISORY

    def advise(self, state: StateSnapshot) -> Optional[IntuitionEvent]:  # pragma: no cover
        raise NotImplementedError

    def hint(
        self,
        *,
        advice: str,
        confidence: float = 0.5,
        rationale: Optional[str] = None,
        evidence_ids: Optional[list[str]] = None,
        target: str = "input",
        scope: str = "episode",
    ) -> IntuitionEvent:
        return IntuitionEvent(
            kind=DirectiveKind.HINT.value,
            advice=advice,
            confidence=confidence,
            rationale=rationale,
            evidence_ids=evidence_ids or [],
            target=target,
            scope=scope,
        )

    def intervene(
        self,
        *,
        advice: str,
        patch: Dict[str, Any],
        confidence: float = 0.6,
        rationale: Optional[str] = None,
        evidence_ids: Optional[list[str]] = None,
        target: str = "input",
        scope: str = "episode",
    ) -> IntuitionEvent:
        return IntuitionEvent(
            kind=DirectiveKind.INTERVENTION.value,
            advice=advice,
            confidence=confidence,
            rationale=rationale,
            evidence_ids=evidence_ids or [],
            patch=patch,
            target=target,
            scope=scope,
        )

    def veto(
        self,
        *,
        advice: str,
        confidence: float = 0.8,
        rationale: Optional[str] = None,
        evidence_ids: Optional[list[str]] = None,
        target: str = "plan",
        scope: str = "episode",
    ) -> IntuitionEvent:
        return IntuitionEvent(
            kind=DirectiveKind.VETO.value,
            advice=advice,
            confidence=confidence,
            rationale=rationale,
            evidence_ids=evidence_ids or [],
            blocking=True,
            target=target,
            scope=scope,
        )


def _parse_uuid(raw: object) -> UUID | None:
    if not isinstance(raw, str):
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


def _looks_like_stable_directive_id(value: str) -> bool:
    return value.startswith("dir-") and len(value) > 4
