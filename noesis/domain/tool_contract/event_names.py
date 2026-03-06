"""Canonical event names for protocol-first tool invocation evidence."""

from __future__ import annotations

TOOL_REQUESTED = "tool.requested"
TOOL_VALIDATED = "tool.validated"
TOOL_REJECTED_INVALID = "tool.rejected.invalid"

TOOL_AUTHN_PASSED = "tool.authn.passed"
TOOL_AUTHN_FAILED = "tool.authn.failed"
TOOL_AUTHZ_PASSED = "tool.authz.passed"
TOOL_AUTHZ_DENIED = "tool.authz.denied"

ACTION_CANDIDATE_EMITTED = "action.candidate_emitted"

TOOL_DRAFT_CREATED = "tool.draft_created"
TOOL_PREFLIGHT_COMPUTED = "tool.preflight.computed"
TOOL_PREFLIGHT_MISMATCH = "tool.preflight.mismatch"
TOOL_PRECONDITION_FAILED = "tool.precondition.failed"

TOOL_APPROVAL_PENDING = "tool.approval.pending"
TOOL_APPROVED = "tool.approved"
TOOL_REJECTED_GOVERNANCE = "tool.rejected.governance"

TOOL_EXECUTION_STARTED = "tool.execution.started"
TOOL_EXECUTION_SUCCEEDED = "tool.execution.succeeded"
TOOL_EXECUTION_FAILED = "tool.execution.failed"

TOOL_REPLAYED = "tool.replayed"
TOOL_RATE_LIMITED = "tool.rate_limited"

ALL_EVENT_NAMES = (
    TOOL_REQUESTED,
    TOOL_VALIDATED,
    TOOL_REJECTED_INVALID,
    TOOL_AUTHN_PASSED,
    TOOL_AUTHN_FAILED,
    TOOL_AUTHZ_PASSED,
    TOOL_AUTHZ_DENIED,
    ACTION_CANDIDATE_EMITTED,
    TOOL_DRAFT_CREATED,
    TOOL_PREFLIGHT_COMPUTED,
    TOOL_PREFLIGHT_MISMATCH,
    TOOL_PRECONDITION_FAILED,
    TOOL_APPROVAL_PENDING,
    TOOL_APPROVED,
    TOOL_REJECTED_GOVERNANCE,
    TOOL_EXECUTION_STARTED,
    TOOL_EXECUTION_SUCCEEDED,
    TOOL_EXECUTION_FAILED,
    TOOL_REPLAYED,
    TOOL_RATE_LIMITED,
)

__all__ = ["ALL_EVENT_NAMES"] + [name for name in globals() if name.startswith("TOOL_") or name == "ACTION_CANDIDATE_EMITTED"]
