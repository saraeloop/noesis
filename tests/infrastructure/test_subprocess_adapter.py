from __future__ import annotations

import sys
from pathlib import Path

from noesis.domain.tool_contract import (
    EffectKind,
    ExecutionContext,
    ExecutionStatus,
    GovernanceContext,
    PayloadEvidence,
    PreparedInvocationStatus,
    PreparedToolInvocation,
    RiskTier,
    SecurityContext,
    ToolIdentity,
    ToolProtocol,
)
from noesis.domain.tool_contract.reason_codes import (
    TOOL_EXECUTION_FAILED,
    TOOL_TIMEOUT,
    TOOL_TRANSPORT_ERROR,
)
from noesis.infrastructure.tool_invocation.adapters import SubprocessToolInvocationAdapter


def test_subprocess_adapter_executes_prepared_read_intent(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("hello from adapter\n", encoding="utf-8")
    invocation = _prepared_subprocess_invocation(
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

    result = SubprocessToolInvocationAdapter().execute(invocation=invocation)

    assert result.status is ExecutionStatus.SUCCEEDED
    assert result.reason_code is None
    assert result.output is not None
    assert result.output["exit_code"] == 0
    assert result.output["stdout"].strip() == "hello from adapter"


def test_subprocess_adapter_maps_missing_executable_to_transport_error() -> None:
    invocation = _prepared_subprocess_invocation(
        payload={
            "argv": ["noesis-missing-executable-016"],
            "cwd": None,
            "env": None,
            "timeout_ms": None,
        }
    )

    result = SubprocessToolInvocationAdapter().execute(invocation=invocation)

    assert result.status is ExecutionStatus.FAILED
    assert result.reason_code == TOOL_TRANSPORT_ERROR


def test_subprocess_adapter_maps_timeout_expired() -> None:
    invocation = _prepared_subprocess_invocation(
        payload={
            "argv": [sys.executable, "-c", "import time; time.sleep(1)"],
            "cwd": None,
            "env": None,
            "timeout_ms": 10,
        }
    )

    result = SubprocessToolInvocationAdapter().execute(invocation=invocation)

    assert result.status is ExecutionStatus.FAILED
    assert result.reason_code == TOOL_TIMEOUT
    assert result.output is not None
    assert result.output["timeout_ms"] == 10


def test_subprocess_adapter_maps_non_zero_exit() -> None:
    invocation = _prepared_subprocess_invocation(
        payload={
            "argv": [sys.executable, "-c", "import sys; sys.exit(3)"],
            "cwd": None,
            "env": None,
            "timeout_ms": None,
        }
    )

    result = SubprocessToolInvocationAdapter().execute(invocation=invocation)

    assert result.status is ExecutionStatus.FAILED
    assert result.reason_code == TOOL_EXECUTION_FAILED
    assert result.output is not None
    assert result.output["exit_code"] == 3


def _prepared_subprocess_invocation(
    *,
    payload: dict[str, object],
) -> PreparedToolInvocation:
    return PreparedToolInvocation(
        run_id="run-1",
        request_id="req-1",
        protocol=ToolProtocol.SUBPROCESS,
        tool=ToolIdentity(namespace="system", name="subprocess", version="1"),
        payload=PayloadEvidence(
            normalized_payload=payload,
            redacted_payload=payload,
            request_fingerprint="sha256:req-1",
            redaction_applied=False,
        ),
        execution=ExecutionContext(timeout_ms=1000, retry_limit=0, idempotency_key="idem-1"),
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
            candidate_id="cand-1",
            requires_approval=False,
            tags=("subprocess",),
        ),
        status=PreparedInvocationStatus.PREPARED,
        draft_id="draft:run-1:req-1",
    )
