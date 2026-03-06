from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

from noesis.domain.tool_contract import (
    EffectKind,
    ExecutionContext,
    ExecutionStatus,
    GovernanceContext,
    IdempotencyDecision,
    IdempotencyEvaluation,
    PayloadEvidence,
    PreparedInvocationStatus,
    PreparedToolInvocation,
    RiskTier,
    SecurityContext,
    ToolExecutionResult,
    ToolIdentity,
    ToolProtocol,
)
from noesis.domain.tool_contract.event_names import TOOL_EXECUTION_FAILED, TOOL_EXECUTION_STARTED, TOOL_EXECUTION_SUCCEEDED
from noesis.domain.tool_contract.reason_codes import (
    TOOL_EXECUTION_FAILED as TOOL_EXECUTION_FAILED_REASON,
    TOOL_TIMEOUT,
    TOOL_TRANSPORT_ERROR,
)
from noesis.infrastructure.tool_invocation.adapters import SubprocessToolInvocationAdapter
from noesis.usecases.tool_invocation import execute_prepared_tool_invocation


class _PreparedRepository:
    def __init__(self, invocation: PreparedToolInvocation) -> None:
        self._invocation = invocation

    def load(self, *, run_id: str, draft_id: str) -> PreparedToolInvocation | None:
        if (run_id, draft_id) == (self._invocation.run_id, self._invocation.draft_id):
            return self._invocation
        return None


class _ApprovalRepository:
    def load(self, *, run_id: str, draft_id: str):
        return None


class _IdempotencyStore:
    def __init__(self) -> None:
        self.recorded: list[tuple[PreparedToolInvocation, ToolExecutionResult]] = []

    def evaluate(self, *, invocation: PreparedToolInvocation) -> IdempotencyEvaluation:
        return IdempotencyEvaluation(
            decision=IdempotencyDecision.NEW,
            fingerprint=invocation.payload.request_fingerprint,
        )

    def record(self, *, invocation: PreparedToolInvocation, result: ToolExecutionResult) -> None:
        self.recorded.append((invocation, result))


class _EventRecorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def record(
        self,
        *,
        run_id: str,
        request_id: str,
        event_name: str,
        payload: Mapping[str, Any],
    ) -> None:
        self.events.append((event_name, dict(payload)))


def test_execute_prepared_tool_invocation_dispatches_subprocess_read_intent(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("hello from use case\n", encoding="utf-8")
    prepared = _prepared_read_invocation(
        payload={
            "argv": [
                sys.executable,
                "-c",
                "from pathlib import Path; print(Path('note.txt').read_text().strip())",
            ],
            "cwd": str(tmp_path),
            "env": None,
            "timeout_ms": None,
        }
    )
    store = _IdempotencyStore()
    recorder = _EventRecorder()

    result = execute_prepared_tool_invocation(
        run_id=prepared.run_id,
        draft_id=prepared.draft_id or "",
        prepared_repository=_PreparedRepository(prepared),
        approval_repository=_ApprovalRepository(),
        idempotency_store=store,
        dispatch=SubprocessToolInvocationAdapter(),
        event_recorder=recorder,
    )

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.output is not None
    assert result.output["stdout"].strip() == "hello from use case"
    assert [name for name, _ in recorder.events] == [
        TOOL_EXECUTION_STARTED,
        TOOL_EXECUTION_SUCCEEDED,
    ]
    assert store.recorded == [(prepared, result)]


def test_execute_prepared_tool_invocation_maps_subprocess_launch_failure() -> None:
    prepared = _prepared_read_invocation(
        payload={
            "argv": ["noesis-missing-executable-016"],
            "cwd": None,
            "env": None,
            "timeout_ms": None,
        }
    )

    result, events = _execute_with_real_adapter(prepared)

    assert result.status is ExecutionStatus.FAILED
    assert result.reason_code == TOOL_TRANSPORT_ERROR
    assert events == [TOOL_EXECUTION_STARTED, TOOL_EXECUTION_FAILED]


def test_execute_prepared_tool_invocation_maps_subprocess_timeout() -> None:
    prepared = _prepared_read_invocation(
        payload={
            "argv": [sys.executable, "-c", "import time; time.sleep(1)"],
            "cwd": None,
            "env": None,
            "timeout_ms": 10,
        }
    )

    result, events = _execute_with_real_adapter(prepared)

    assert result.status is ExecutionStatus.FAILED
    assert result.reason_code == TOOL_TIMEOUT
    assert events == [TOOL_EXECUTION_STARTED, TOOL_EXECUTION_FAILED]


def test_execute_prepared_tool_invocation_maps_subprocess_non_zero_exit() -> None:
    prepared = _prepared_read_invocation(
        payload={
            "argv": [sys.executable, "-c", "import sys; sys.exit(7)"],
            "cwd": None,
            "env": None,
            "timeout_ms": None,
        }
    )

    result, events = _execute_with_real_adapter(prepared)

    assert result.status is ExecutionStatus.FAILED
    assert result.reason_code == TOOL_EXECUTION_FAILED_REASON
    assert result.output is not None
    assert result.output["exit_code"] == 7
    assert events == [TOOL_EXECUTION_STARTED, TOOL_EXECUTION_FAILED]


def _execute_with_real_adapter(prepared: PreparedToolInvocation) -> tuple[ToolExecutionResult, list[str]]:
    recorder = _EventRecorder()
    result = execute_prepared_tool_invocation(
        run_id=prepared.run_id,
        draft_id=prepared.draft_id or "",
        prepared_repository=_PreparedRepository(prepared),
        approval_repository=_ApprovalRepository(),
        idempotency_store=_IdempotencyStore(),
        dispatch=SubprocessToolInvocationAdapter(),
        event_recorder=recorder,
    )
    return result, [name for name, _ in recorder.events]


def _prepared_read_invocation(*, payload: dict[str, object]) -> PreparedToolInvocation:
    return PreparedToolInvocation(
        run_id="run-subprocess",
        request_id="req-subprocess",
        protocol=ToolProtocol.SUBPROCESS,
        tool=ToolIdentity(namespace="system", name="subprocess", version="1"),
        payload=PayloadEvidence(
            normalized_payload=payload,
            redacted_payload=payload,
            request_fingerprint="sha256:subprocess-read",
            redaction_applied=False,
        ),
        execution=ExecutionContext(timeout_ms=1_000, retry_limit=0, idempotency_key="idem-subprocess"),
        security=SecurityContext(
            principal_id="user:123",
            scopes=("tool:read",),
            policy_scope="repo/main",
            authn_method="test",
            credential_ref=None,
        ),
        governance=GovernanceContext(
            effect_kind=EffectKind.READ,
            risk_tier=RiskTier.LOW,
            candidate_id="cand-subprocess",
            requires_approval=False,
            tags=("subprocess",),
        ),
        status=PreparedInvocationStatus.PREPARED,
        draft_id="draft:run-subprocess:req-subprocess",
    )
