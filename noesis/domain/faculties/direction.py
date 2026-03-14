"""Directional directives and policy helpers for Noēsis."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Dict, Mapping, Optional, Sequence
from uuid import UUID, uuid4

from .intuition import (
    Intuition,
    IntuitionAssessment,
    IntuitionEvent,
    IntuitionMode,
    PolicyKind,
    RiskLevel,
    SalienceSignal,
    ScrutinyLevel,
    StateSnapshot,
    StrategyHint,
    ToolConstraint,
)
from .identifiers import DirectiveIdentifier, make_directive_identifier
from .versioning import current_version, is_compatible

__all__ = [
    "DirectiveKind",
    "DirectiveStatus",
    "DirectiveDiff",
    "PlannerDirective",
    "DirectedIntuition",
    "planner_directive_from_intuition",
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
    intuition_event_id: str | None = None
    risk_level: RiskLevel | None = None
    salience_signals: tuple[SalienceSignal, ...] = ()
    strategy_hints: tuple[StrategyHint, ...] = ()
    tool_constraints: tuple[ToolConstraint, ...] = ()
    scrutiny_level: ScrutinyLevel | None = None
    evidence_ids: tuple[str, ...] = ()

    def to_mapping(self) -> Dict[str, Any]:
        """Render the directive into a JSON-serializable mapping."""
        payload: Dict[str, Any] = {
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
        if self.intuition_event_id:
            payload["intuition_event_id"] = self.intuition_event_id
        if self.risk_level is not None:
            payload["risk_level"] = self.risk_level.value
        if self.salience_signals:
            payload["salience_signals"] = [signal.value for signal in self.salience_signals]
        if self.strategy_hints:
            payload["strategy_hints"] = [hint.value for hint in self.strategy_hints]
        if self.tool_constraints:
            payload["tool_constraints"] = [constraint.value for constraint in self.tool_constraints]
        if self.scrutiny_level is not None:
            payload["scrutiny_level"] = self.scrutiny_level.value
        if self.evidence_ids:
            payload["evidence_ids"] = list(self.evidence_ids)
        return payload

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
        evidence_source = payload.get("evidence_ids")
        if not isinstance(evidence_source, (list, tuple)):
            evidence_source = ()
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
            intuition_event_id=str(payload["intuition_event_id"]) if payload.get("intuition_event_id") else None,
            risk_level=_coerce_optional_enum(payload.get("risk_level"), RiskLevel),
            salience_signals=_coerce_enum_sequence(payload.get("salience_signals"), SalienceSignal),
            strategy_hints=_coerce_enum_sequence(payload.get("strategy_hints"), StrategyHint),
            tool_constraints=_coerce_enum_sequence(payload.get("tool_constraints"), ToolConstraint),
            scrutiny_level=_coerce_optional_enum(payload.get("scrutiny_level"), ScrutinyLevel),
            evidence_ids=tuple(str(value) for value in evidence_source),
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
        risk_level: RiskLevel | None = None,
        salience_signals: Sequence[SalienceSignal] | None = None,
        strategy_hints: Sequence[StrategyHint] | None = None,
        tool_constraints: Sequence[ToolConstraint] | None = None,
        scrutiny_level: ScrutinyLevel | None = None,
    ) -> IntuitionEvent:
        return IntuitionEvent(
            kind=DirectiveKind.HINT.value,
            advice=advice,
            confidence=confidence,
            rationale=rationale,
            evidence_ids=evidence_ids or [],
            target=target,
            scope=scope,
            risk_level=risk_level,
            salience_signals=tuple(salience_signals or ()),
            strategy_hints=tuple(strategy_hints or ()),
            tool_constraints=tuple(tool_constraints or ()),
            scrutiny_level=scrutiny_level,
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
        risk_level: RiskLevel | None = None,
        salience_signals: Sequence[SalienceSignal] | None = None,
        strategy_hints: Sequence[StrategyHint] | None = None,
        tool_constraints: Sequence[ToolConstraint] | None = None,
        scrutiny_level: ScrutinyLevel | None = None,
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
            risk_level=risk_level,
            salience_signals=tuple(salience_signals or ()),
            strategy_hints=tuple(strategy_hints or ()),
            tool_constraints=tuple(tool_constraints or ()),
            scrutiny_level=scrutiny_level,
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
        risk_level: RiskLevel | None = RiskLevel.CRITICAL,
        salience_signals: Sequence[SalienceSignal] | None = (SalienceSignal.SAFETY_BOUNDARY,),
        strategy_hints: Sequence[StrategyHint] | None = (StrategyHint.CONSERVATIVE, StrategyHint.VERIFY_FIRST),
        tool_constraints: Sequence[ToolConstraint] | None = (
            ToolConstraint.NO_SIDE_EFFECTS,
            ToolConstraint.REQUIRE_DOUBLE_CHECK,
        ),
        scrutiny_level: ScrutinyLevel | None = ScrutinyLevel.STRICT,
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
            risk_level=risk_level,
            salience_signals=tuple(salience_signals or ()),
            strategy_hints=tuple(strategy_hints or ()),
            tool_constraints=tuple(tool_constraints or ()),
            scrutiny_level=scrutiny_level,
        )


def planner_directive_from_intuition(
    *,
    directive: PlannerDirective,
    intuition_event_id: str | None,
    assessment: IntuitionAssessment | None,
) -> PlannerDirective:
    """Attach intuition-consumption evidence to a planner directive."""

    if assessment is None:
        return directive
    return PlannerDirective(
        steps=directive.steps,
        status=directive.status,
        reason=directive.reason,
        diff=directive.diff,
        applied=directive.applied,
        policy_id=directive.policy_id,
        policy_version=directive.policy_version,
        policy_kind=directive.policy_kind,
        directive_id=directive.directive_id,
        legacy_directive_id=directive.legacy_directive_id,
        intuition_event_id=intuition_event_id,
        risk_level=assessment.risk_level,
        salience_signals=assessment.salience_signals,
        strategy_hints=assessment.strategy_hints,
        tool_constraints=assessment.tool_constraints,
        scrutiny_level=assessment.scrutiny_level,
        evidence_ids=assessment.evidence_ids,
    )


def _parse_uuid(raw: object) -> UUID | None:
    if not isinstance(raw, str):
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


def _coerce_enum_sequence(values: object, enum_type: type[Enum]) -> tuple[Enum, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    result: list[Enum] = []
    for value in values:
        if isinstance(value, enum_type):
            result.append(value)
            continue
        try:
            result.append(enum_type(str(value)))
        except ValueError:
            continue
    return tuple(result)


def _coerce_optional_enum(value: object, enum_type: type[Enum]) -> Enum | None:
    if value is None:
        return None
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(str(value))
    except ValueError:
        return None


def _looks_like_stable_directive_id(value: str) -> bool:
    return value.startswith("dir-") and len(value) > 4
