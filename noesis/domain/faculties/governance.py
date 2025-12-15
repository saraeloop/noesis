"""
Governance policy contracts for Noēsis.

This module defines the immutable, versioned data structures used to represent
the outcome of governance evaluations inside the cognitive loop. These contracts
form part of the stable external interface that adapters, policies, and auditing
systems rely on.

- GovernanceDecision: enumerates the canonical decisions a policy can return.
- GovernanceResult: a frozen dataclass encapsulating the decision, policy
  metadata, scoring rationale, and any structured details suitable for JSON
  serialization.

These objects are pure domain entities—free of side effects, runtime state, or
infrastructure dependencies—and may be safely persisted, logged, or exchanged
across process boundaries.
"""


from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, ClassVar, Dict, Mapping, Optional, Sequence
from uuid import UUID, uuid4

from noesis.domain.state import PlanStep
from .identifiers import GovernanceIdentifier, make_governance_identifier
from .versioning import current_version, is_compatible

__all__ = [
    "GovernanceDecision",
    "GovernanceResult",
    "GovernanceMode",
    "GovernanceFailurePolicy",
    "PreActGovernor",
    "with_governance_context",
]


class GovernanceDecision(str, Enum):
    """Available governance outcomes."""

    ALLOW = "allow"
    AUDIT = "audit"
    VETO = "veto"


class GovernanceMode(str, Enum):
    """Runtime mode for governance evaluation."""

    OFF = "off"
    AUDIT = "audit"
    ENFORCE = "enforce"


class GovernanceFailurePolicy(str, Enum):
    """How to handle governance errors/timeouts."""

    FAIL_OPEN = "fail_open"
    FAIL_CLOSED = "fail_closed"

    @classmethod
    def default_for(cls, mode: GovernanceMode) -> "GovernanceFailurePolicy":
        if mode is GovernanceMode.AUDIT:
            return cls.FAIL_OPEN
        if mode is GovernanceMode.ENFORCE:
            return cls.FAIL_CLOSED
        return cls.FAIL_OPEN


@dataclass(frozen=True, slots=True)
class GovernanceResult:
    """
    Immutable, versioned result of a governance policy evaluation.

    A GovernanceResult represents the verdict issued by a policy when applied to
    a pending cognitive action (typically pre-act). It is designed for
    serialization, audit, and downstream analytics.

    Attributes:
        schema_version: Version identifier for compatibility tracking.
        decision: One of the GovernanceDecision values (allow, audit, veto).
        rule_id: Identifier of the rule or check that produced this result.
        score: Confidence or severity score in [0.0, 1.0].
        message: Human-readable explanation or justification.
        policy_id: Optional identifier of the policy source.
        policy_version: Optional version string of the policy.
        details: Optional structured diagnostic or contextual data.
        mode: Optional governance mode used during evaluation.
        failure_policy: Optional failure handling applied during evaluation.
        enforced: True when the decision will affect control flow.
        error: Optional structured error metadata when evaluation fails.

    This class is side-effect-free and safe to persist or transmit as JSON.
    """

    schema_version: ClassVar[str] = current_version("governance")
    decision: GovernanceDecision
    rule_id: str
    score: float
    message: str
    policy_id: str = "unspecified"
    policy_version: str = "0.0.0"
    policy_kind: str = "rules"
    details: Optional[Dict[str, Any]] = None
    mode: GovernanceMode | None = None
    failure_policy: GovernanceFailurePolicy | None = None
    enforced: bool = False
    error: Optional[Dict[str, Any]] = None
    governance_id: GovernanceIdentifier | None = None
    decision_id: UUID = field(default_factory=uuid4)

    def to_mapping(self) -> Dict[str, Any]:
        """Render the decision as a JSON-serializable dict."""
        payload: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "governance_id": str(self.governance_id),
            "decision_id": str(self.decision_id),
            "decision": self.decision.value,
            "rule_id": self.rule_id,
            "score": self.score,
            "message": self.message,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_kind": self.policy_kind,
        }
        if self.details:
            payload["details"] = dict(self.details)
        if self.mode:
            payload["mode"] = self.mode.value
        if self.failure_policy:
            payload["failure_policy"] = self.failure_policy.value
        payload["enforced"] = bool(self.enforced)
        if self.error:
            payload["error"] = dict(self.error)
        return payload

    def __post_init__(self) -> None:
        if self.policy_kind not in ("llm", "rules", "hybrid"):
            raise ValueError(f"Invalid policy_kind '{self.policy_kind}' for GovernanceResult")
        identifier = self.governance_id
        if isinstance(identifier, GovernanceIdentifier):
            computed = identifier
        elif isinstance(identifier, str) and _looks_like_governance_id(identifier):
            computed = GovernanceIdentifier(identifier)
        else:
            computed = make_governance_identifier(
                policy_id=self.policy_id,
                policy_version=self.policy_version,
                policy_kind=self.policy_kind,
                decision=self.decision.value,
                rule_id=self.rule_id,
                score=self.score,
                message=self.message,
                details=self.details or {},
            )
        object.__setattr__(self, "governance_id", computed)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "GovernanceResult":
        """Rehydrate a decision from a serialized mapping."""
        version = str(payload.get("schema_version", cls.schema_version))
        if not is_compatible(version, cls.schema_version):
            raise ValueError(
                f"Incompatible governance schema version '{version}' (expected ≤ {cls.schema_version})"
            )
        decision_raw = payload.get("decision", GovernanceDecision.AUDIT.value)
        try:
            decision = GovernanceDecision(decision_raw)
        except ValueError:
            decision = GovernanceDecision.AUDIT
        governance_id_raw = payload.get("governance_id")
        decision_id_raw = payload.get("decision_id")
        try:
            decision_id = UUID(str(decision_id_raw)) if decision_id_raw else uuid4()
        except (TypeError, ValueError):
            decision_id = uuid4()
        policy_kind = payload.get("policy_kind", "rules")
        if policy_kind not in ("llm", "rules", "hybrid"):
            policy_kind = "rules"
        details = payload.get("details")
        if details is not None and not isinstance(details, dict):
            details = None
        mode_raw = payload.get("mode")
        mode = GovernanceMode(mode_raw) if isinstance(mode_raw, str) and mode_raw in GovernanceMode._value2member_map_ else None
        failure_policy_raw = payload.get("failure_policy")
        failure_policy = (
            GovernanceFailurePolicy(failure_policy_raw)
            if isinstance(failure_policy_raw, str) and failure_policy_raw in GovernanceFailurePolicy._value2member_map_
            else None
        )
        enforced = bool(payload.get("enforced", False))
        error = payload.get("error")
        if error is not None and not isinstance(error, dict):
            error = None
        governance_identifier: GovernanceIdentifier | None = None
        if isinstance(governance_id_raw, str) and _looks_like_governance_id(governance_id_raw):
            governance_identifier = GovernanceIdentifier(governance_id_raw)
        if governance_identifier is None:
            governance_identifier = make_governance_identifier(
                policy_id=str(payload.get("policy_id", "unspecified")),
                policy_version=str(payload.get("policy_version", "0.0.0")),
                policy_kind=policy_kind,
                decision=decision.value,
                rule_id=str(payload.get("rule_id", "unspecified")),
                score=float(payload.get("score", 0.0)),
                message=str(payload.get("message", "")),
                details=details or {},
            )
        return cls(
            governance_id=governance_identifier,
            decision_id=decision_id,
            decision=decision,
            rule_id=str(payload.get("rule_id", "unspecified")),
            score=float(payload.get("score", 0.0)),
            message=str(payload.get("message", "")),
            policy_id=str(payload.get("policy_id", "unspecified")),
            policy_version=str(payload.get("policy_version", "0.0.0")),
            policy_kind=policy_kind,
            details=details,
            mode=mode,
            failure_policy=failure_policy,
            enforced=enforced,
            error=error,
        )


def with_governance_context(
    result: GovernanceResult,
    *,
    mode: GovernanceMode,
    failure_policy: GovernanceFailurePolicy | None,
    enforced: bool,
    error: Optional[Dict[str, Any]] = None,
) -> GovernanceResult:
    """
    Attach runtime governance metadata to a pure policy result.

    This preserves immutability while threading mode/failure_policy/enforced
    into the emitted payload.
    """
    return replace(
        result,
        mode=mode,
        failure_policy=failure_policy or GovernanceFailurePolicy.default_for(mode),
        enforced=enforced,
        error=error,
    )


def _looks_like_governance_id(value: str) -> bool:
    return value.startswith("gov-") and len(value) > 4


@dataclass(slots=True)
class PreActGovernor:
    """Simple rule-based governor for pre-act evaluation."""

    policy_id: str = "governance.rules"
    policy_version: str = "1.0.0"
    policy_kind: str = "rules"

    def evaluate(
        self,
        *,
        goal: str,
        plan: Sequence[PlanStep],
    ) -> GovernanceResult:
        goal_lower = goal.lower()
        if "danger" in goal_lower or any("danger" in step.description.lower() for step in plan):
            return GovernanceResult(
                decision=GovernanceDecision.VETO,
                rule_id="rules.veto.danger",
                score=0.95,
                message="Task flagged as dangerous",
                policy_id=self.policy_id,
                policy_version=self.policy_version,
                policy_kind=self.policy_kind,
                details={"goal": goal},
            )

        sensitive_pattern = re.compile(r"\b(write|delete|drop)\b", re.IGNORECASE)
        veto_pattern = re.compile(r"\b(veto|destroy|shutdown|wipe)\b", re.IGNORECASE)
        if veto_pattern.search(goal) or any(veto_pattern.search(step.description) for step in plan):
            return GovernanceResult(
                decision=GovernanceDecision.VETO,
                rule_id="rules.veto.protected",
                score=0.95,
                message="Task blocked by governance policy",
                policy_id=self.policy_id,
                policy_version=self.policy_version,
                policy_kind=self.policy_kind,
                details={"goal": goal},
            )
        if sensitive_pattern.search(goal) or any(sensitive_pattern.search(step.description) for step in plan):
            return GovernanceResult(
                decision=GovernanceDecision.AUDIT,
                rule_id="rules.audit.sensitive",
                score=0.6,
                message="Sensitive action requires review",
                policy_id=self.policy_id,
                policy_version=self.policy_version,
                policy_kind=self.policy_kind,
                details={"goal": goal},
            )

        return GovernanceResult(
            decision=GovernanceDecision.ALLOW,
            rule_id="rules.allow.default",
            score=0.1,
            message="",
            policy_id=self.policy_id,
            policy_version=self.policy_version,
            policy_kind=self.policy_kind,
            details={"goal": goal},
        )
