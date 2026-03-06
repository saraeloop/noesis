"""Filesystem-backed repositories for durable ADR-016 tool invocation state."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
from typing import Any, Mapping

from noesis.domain.tool_contract import (
    ApprovalDecisionStatus,
    AmbiguousPreparedToolInvocationError,
    EffectKind,
    ExecutionContext,
    GovernanceContext,
    IdempotencyDecision,
    IdempotencyEvaluation,
    IdempotencyScope,
    PayloadEvidence,
    PreflightBinding,
    PreparedInvocationStatus,
    PreparedToolInvocation,
    RiskTier,
    SecurityContext,
    ToolApprovalDecision,
    ToolExecutionResult,
    ToolIdentity,
    ToolProtocol,
    evaluate_idempotency,
)
from noesis.runtime.serialization import atomic_write_json

_PREPARED_DIR = Path("tool_invocations") / "prepared"
_APPROVALS_DIR = Path("tool_invocations") / "approvals"
_IDEMPOTENCY_DIR = Path("tool_invocations") / "idempotency"


class FilePreparedInvocationRepository:
    """Persist prepared tool drafts inside the run directory."""

    def __init__(self, *, run_dir: Path) -> None:
        self._run_dir = run_dir

    def save(self, invocation: PreparedToolInvocation) -> None:
        atomic_write_json(self._path_for(invocation.draft_id or invocation.request_id), _prepared_to_dict(invocation))

    def load(self, *, run_id: str, draft_id: str) -> PreparedToolInvocation | None:
        payload = _read_json(self._path_for(draft_id))
        if payload is None or str(payload.get("run_id")) != run_id:
            return None
        return _prepared_from_dict(payload)

    def load_pending_for_run(self, *, run_id: str) -> PreparedToolInvocation | None:
        matches: list[PreparedToolInvocation] = []
        root = self._run_dir / _PREPARED_DIR
        if not root.exists():
            return None
        for path in sorted(root.glob("*.json")):
            payload = _read_json(path)
            if payload is None or str(payload.get("run_id")) != run_id:
                continue
            invocation = _prepared_from_dict(payload)
            if invocation.status is PreparedInvocationStatus.PENDING_APPROVAL:
                matches.append(invocation)
        if not matches:
            return None
        if len(matches) > 1:
            raise AmbiguousPreparedToolInvocationError(
                f"multiple pending prepared invocations exist for run_id={run_id!r}"
            )
        return matches[0]

    def _path_for(self, draft_id: str) -> Path:
        return self._run_dir / _PREPARED_DIR / f"{draft_id}.json"


class FileApprovalDecisionRepository:
    """Persist approval decisions bound to prepared tool drafts."""

    def __init__(self, *, run_dir: Path) -> None:
        self._run_dir = run_dir

    def save(self, decision: ToolApprovalDecision) -> None:
        draft_id = decision.draft_id or decision.request_id
        atomic_write_json(self._run_dir / _APPROVALS_DIR / f"{draft_id}.json", _approval_to_dict(decision))

    def load(self, *, run_id: str, draft_id: str) -> ToolApprovalDecision | None:
        payload = _read_json(self._run_dir / _APPROVALS_DIR / f"{draft_id}.json")
        if payload is None or str(payload.get("run_id")) != run_id:
            return None
        return _approval_from_dict(payload)


class FileIdempotencyStore:
    """Persist idempotency decisions inside the run directory."""

    def __init__(self, *, run_dir: Path) -> None:
        self._run_dir = run_dir

    def evaluate(self, *, invocation: PreparedToolInvocation) -> IdempotencyEvaluation:
        scope = _scope_for(invocation)
        if scope is None:
            return IdempotencyEvaluation(
                decision=IdempotencyDecision.NEW,
                fingerprint=invocation.payload.request_fingerprint,
            )
        payload = _read_json(self._path_for(scope))
        return evaluate_idempotency(
            incoming_fingerprint=invocation.payload.request_fingerprint,
            existing_fingerprint=None if payload is None else _string_or_none(payload.get("fingerprint")),
            existing_execution_id=None if payload is None else _string_or_none(payload.get("execution_id")),
        )

    def record(
        self,
        *,
        invocation: PreparedToolInvocation,
        result: ToolExecutionResult,
    ) -> None:
        scope = _scope_for(invocation)
        if scope is None:
            return
        atomic_write_json(
            self._path_for(scope),
            {
                "principal_id": scope.principal_id,
                "tool_key": scope.tool_key,
                "idempotency_key": scope.idempotency_key,
                "fingerprint": invocation.payload.request_fingerprint,
                "execution_id": result.execution_id,
            },
        )

    def _path_for(self, scope: IdempotencyScope) -> Path:
        safe = scope.idempotency_key.replace("/", "_")
        return self._run_dir / _IDEMPOTENCY_DIR / f"{scope.principal_id}__{scope.tool_key}__{safe}.json"


def _scope_for(invocation: PreparedToolInvocation) -> IdempotencyScope | None:
    key = invocation.execution.idempotency_key
    if not key:
        return None
    tool_key = ".".join(part for part in (invocation.protocol.value, invocation.tool.namespace, invocation.tool.name, invocation.tool.version or "") if part)
    return IdempotencyScope(
        principal_id=invocation.security.principal_id,
        tool_key=tool_key,
        idempotency_key=key,
    )


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _prepared_to_dict(invocation: PreparedToolInvocation) -> dict[str, Any]:
    return asdict(invocation)


def _approval_to_dict(decision: ToolApprovalDecision) -> dict[str, Any]:
    return asdict(decision)


def _prepared_from_dict(payload: Mapping[str, Any]) -> PreparedToolInvocation:
    preflight_payload = payload.get("preflight")
    preflight = None
    if isinstance(preflight_payload, Mapping):
        preflight = PreflightBinding(
            impact_hash=str(preflight_payload.get("impact_hash", "")),
            witness=_mapping_or_none(preflight_payload.get("witness")),
        )
    payload_payload = _mapping(payload.get("payload"))
    payload_obj = PayloadEvidence(
        normalized_payload=dict(_mapping_or_empty(payload_payload, "normalized_payload")),
        redacted_payload=dict(_mapping_or_empty(payload_payload, "redacted_payload")),
        request_fingerprint=str(payload_payload.get("request_fingerprint", "")),
        redaction_applied=bool(payload_payload.get("redaction_applied", False)),
    )
    execution_payload = _mapping_or_empty(payload, "execution")
    security_payload = _mapping_or_empty(payload, "security")
    governance_payload = _mapping_or_empty(payload, "governance")
    tool_payload = _mapping_or_empty(payload, "tool")
    return PreparedToolInvocation(
        run_id=str(payload.get("run_id", "")),
        request_id=str(payload.get("request_id", "")),
        protocol=ToolProtocol(str(payload.get("protocol", ToolProtocol.SUBPROCESS.value))),
        tool=ToolIdentity(
            namespace=str(tool_payload.get("namespace", "")),
            name=str(tool_payload.get("name", "")),
            version=_string_or_none(tool_payload.get("version")),
        ),
        payload=payload_obj,
        execution=ExecutionContext(
            timeout_ms=int(execution_payload.get("timeout_ms", 0)),
            retry_limit=int(execution_payload.get("retry_limit", 0)),
            idempotency_key=_string_or_none(execution_payload.get("idempotency_key")),
        ),
        security=SecurityContext(
            principal_id=str(security_payload.get("principal_id", "")),
            scopes=tuple(str(item) for item in security_payload.get("scopes", ())),
            policy_scope=str(security_payload.get("policy_scope", "")),
            authn_method=_string_or_none(security_payload.get("authn_method")),
            credential_ref=_string_or_none(security_payload.get("credential_ref")),
        ),
        governance=GovernanceContext(
            effect_kind=EffectKind(str(governance_payload.get("effect_kind", EffectKind.READ.value))),
            risk_tier=RiskTier(str(governance_payload.get("risk_tier", RiskTier.LOW.value))),
            candidate_id=_string_or_none(governance_payload.get("candidate_id")),
            requires_approval=bool(governance_payload.get("requires_approval", False)),
            tags=tuple(str(item) for item in governance_payload.get("tags", ())),
        ),
        status=PreparedInvocationStatus(str(payload.get("status", PreparedInvocationStatus.PREPARED.value))),
        schema_version=str(payload.get("schema_version", "tool_contract/1.0.0")),
        draft_id=_string_or_none(payload.get("draft_id")),
        preflight=preflight,
    )


def _approval_from_dict(payload: Mapping[str, Any]) -> ToolApprovalDecision:
    return ToolApprovalDecision(
        decision_id=str(payload.get("decision_id", "")),
        run_id=str(payload.get("run_id", "")),
        request_id=str(payload.get("request_id", "")),
        candidate_id=_string_or_none(payload.get("candidate_id")),
        draft_id=_string_or_none(payload.get("draft_id")),
        status=ApprovalDecisionStatus(str(payload.get("status", ApprovalDecisionStatus.APPROVED.value))),
        schema_version=str(payload.get("schema_version", "tool_contract/1.0.0")),
        reason_code=_string_or_none(payload.get("reason_code")),
        reviewed_fingerprint=_string_or_none(payload.get("reviewed_fingerprint")),
        impact_hash=_string_or_none(payload.get("impact_hash")),
        approver_id=_string_or_none(payload.get("approver_id")),
        approval_token_ref=_string_or_none(payload.get("approval_token_ref")),
    )


def _mapping_or_empty(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, Mapping) else {}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_or_none(value: object) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


__all__ = [
    "FileApprovalDecisionRepository",
    "FileIdempotencyStore",
    "FilePreparedInvocationRepository",
]
