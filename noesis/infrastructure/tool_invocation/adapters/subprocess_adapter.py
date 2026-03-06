"""Subprocess protocol adapter for prepared tool invocation dispatch."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from noesis.domain.tool_contract import (
    ExecutionStatus,
    PreparedToolInvocation,
    ToolExecutionResult,
    ToolProtocol,
)
from noesis.domain.tool_contract.reason_codes import (
    TOOL_EXECUTION_FAILED,
    TOOL_INVALID_PAYLOAD,
    TOOL_TIMEOUT,
    TOOL_TRANSPORT_ERROR,
    TOOL_UNSUPPORTED_PROTOCOL,
)

AllowedPayload = Mapping[str, Any]
SubprocessRunner = Callable[..., subprocess.CompletedProcess[str]]


@dataclass(frozen=True, slots=True)
class NormalizedSubprocessRequest:
    """Normalized subprocess request extracted from payload evidence."""

    argv: tuple[str, ...]
    cwd: str | None
    env: dict[str, str] | None
    timeout_ms: int | None


@dataclass(frozen=True, slots=True)
class SubprocessToolInvocationAdapter:
    """Dispatch prepared subprocess intents through `subprocess.run`."""

    runner: SubprocessRunner = subprocess.run

    def execute(self, *, invocation: PreparedToolInvocation) -> ToolExecutionResult:
        """Execute one prepared subprocess invocation."""

        execution_id = _execution_id_for(invocation)
        if invocation.protocol is not ToolProtocol.SUBPROCESS:
            return ToolExecutionResult(
                request_id=invocation.request_id,
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                reason_code=TOOL_UNSUPPORTED_PROTOCOL,
                preflight=invocation.preflight,
                output={"protocol": invocation.protocol.value},
            )

        try:
            request = _build_subprocess_request(
                payload=invocation.payload.normalized_payload,
                default_timeout_ms=invocation.execution.timeout_ms,
            )
        except ValueError as exc:
            return ToolExecutionResult(
                request_id=invocation.request_id,
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                reason_code=TOOL_INVALID_PAYLOAD,
                preflight=invocation.preflight,
                output={"error": str(exc)},
            )

        timeout_seconds = None if request.timeout_ms is None else max(request.timeout_ms, 1) / 1000.0
        try:
            completed = self.runner(
                list(request.argv),
                cwd=request.cwd,
                env=request.env,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            return ToolExecutionResult(
                request_id=invocation.request_id,
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                reason_code=TOOL_TIMEOUT,
                preflight=invocation.preflight,
                output={
                    "argv": list(request.argv),
                    "cwd": request.cwd,
                    "timeout_ms": request.timeout_ms,
                    "stdout": _coerce_stream(exc.stdout),
                    "stderr": _coerce_stream(exc.stderr),
                },
            )
        except OSError as exc:
            return ToolExecutionResult(
                request_id=invocation.request_id,
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                reason_code=TOOL_TRANSPORT_ERROR,
                preflight=invocation.preflight,
                output={
                    "argv": list(request.argv),
                    "cwd": request.cwd,
                    "error": str(exc),
                },
            )

        result_payload = {
            "argv": list(request.argv),
            "cwd": request.cwd,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        if completed.returncode != 0:
            return ToolExecutionResult(
                request_id=invocation.request_id,
                execution_id=execution_id,
                status=ExecutionStatus.FAILED,
                reason_code=TOOL_EXECUTION_FAILED,
                preflight=invocation.preflight,
                output=result_payload,
            )

        return ToolExecutionResult(
            request_id=invocation.request_id,
            execution_id=execution_id,
            status=ExecutionStatus.SUCCEEDED,
            preflight=invocation.preflight,
            output=result_payload,
        )


def _build_subprocess_request(
    *,
    payload: AllowedPayload,
    default_timeout_ms: int | None,
) -> NormalizedSubprocessRequest:
    allowed_keys = {"argv", "cwd", "env", "timeout_ms"}
    unknown_keys = set(payload) - allowed_keys
    if unknown_keys:
        unknown = ", ".join(sorted(unknown_keys))
        raise ValueError(f"unexpected subprocess payload field(s): {unknown}")

    raw_argv = payload.get("argv")
    if not isinstance(raw_argv, list) or not raw_argv or not all(isinstance(item, str) for item in raw_argv):
        raise ValueError("subprocess payload requires non-empty argv: list[str]")

    raw_cwd = payload.get("cwd")
    if raw_cwd is not None and not isinstance(raw_cwd, str):
        raise ValueError("subprocess payload cwd must be str | None")

    raw_env = payload.get("env")
    if raw_env is not None:
        if not isinstance(raw_env, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in raw_env.items()
        ):
            raise ValueError("subprocess payload env must be dict[str, str] | None")
        env = dict(raw_env)
    else:
        env = None

    raw_timeout_ms = payload.get("timeout_ms", default_timeout_ms)
    if raw_timeout_ms is not None and (not isinstance(raw_timeout_ms, int) or raw_timeout_ms <= 0):
        raise ValueError("subprocess payload timeout_ms must be int > 0 | None")

    return NormalizedSubprocessRequest(
        argv=tuple(raw_argv),
        cwd=raw_cwd,
        env=env,
        timeout_ms=raw_timeout_ms,
    )


def _execution_id_for(invocation: PreparedToolInvocation) -> str:
    draft_or_request = invocation.draft_id or invocation.request_id
    return f"exec:{invocation.run_id}:{draft_or_request}"


def _coerce_stream(value: str | bytes | None) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return value.decode("utf-8", errors="replace")


__all__ = [
    "NormalizedSubprocessRequest",
    "SubprocessToolInvocationAdapter",
]
