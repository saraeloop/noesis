"""
Exception hierarchy for Noēsis.

Defines the system’s control boundaries, where reasoning escalates into
explicit failure or veto. These exceptions mark deliberate interruptions
in an agent’s cognitive loop, ensuring that intervention remains safe,
auditable, and intentional.
"""

from __future__ import annotations


class NoesisError(Exception):
    """Base class for framework-level errors."""


class NoesisVeto(NoesisError):
    """Raised when a governance or intuition policy vetoes an action or episode."""

    def __init__(
        self,
        *,
        advice: str,
        target: str,
        scope: str,
        decision: str | None = None,
        rule_id: str | None = None,
        policy_id: str | None = None,
        policy_version: str | None = None,
        policy_kind: str | None = None,
        enforced: bool | None = None,
        details: object | None = None,
        error: object | None = None,
        governance_id: str | None = None,
        action_candidate_id: str | None = None,
    ) -> None:
        super().__init__(advice)
        self.advice = advice
        self.target = target
        self.scope = scope
        self.decision = decision
        self.rule_id = rule_id
        self.policy_id = policy_id
        self.policy_version = policy_version
        self.policy_kind = policy_kind
        self.enforced = enforced
        self.details = details
        self.error = error
        self.governance_id = governance_id
        self.action_candidate_id = action_candidate_id
