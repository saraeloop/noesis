# ADR-016 PR-3: Subprocess Adapter Proof

## Intent

Document the first real protocol adapter that executes through the ADR-016 prepare/execute contract.

This note is for contributors working on tool invocation internals. It is not a new public API surface.

## Scope and non-goals

In scope (implemented):

- Prepared tool intents can execute through a concrete `ToolDispatchPort`.
- `subprocess` is the first protocol adapter wired through the use case seam.
- Subprocess outcomes are mapped to canonical `ToolExecutionResult` status/reason codes.

Out of scope (still pending):

- HTTP adapter
- MCP adapter
- ADR-015/017 resume bridge for prepared intents
- New public API surface

## Architecture and codepaths

- Domain contract: `noesis/domain/tool_contract`
- Prepare use case: `noesis/usecases/tool_invocation/prepare_tool_invocation.py`
- Execute use case: `noesis/usecases/tool_invocation/execute_prepared_tool_invocation.py`
- Dispatch port: `noesis/usecases/tool_invocation/ports.py` (`ToolDispatchPort`)
- Subprocess adapter: `noesis/infrastructure/tool_invocation/adapters/subprocess_adapter.py`
- Adapter tests: `tests/infrastructure/test_subprocess_adapter.py`
- End-to-end dispatch proof: `tests/tool_contract/core/test_execute_prepared_subprocess_adapter.py`

## Workflow: prepare -> execute

1. `prepare_tool_invocation(...)` validates, authenticates, authorizes, emits candidate evidence, and persists a `PreparedToolInvocation`.
2. `execute_prepared_tool_invocation(...)` loads the prepared draft, applies approval/idempotency rules, emits execution events, and calls `dispatch.execute(invocation=prepared)`.
3. `SubprocessToolInvocationAdapter.execute(...)` runs `subprocess.run(...)` and returns a canonical `ToolExecutionResult`.

Execution use-case event behavior:

- Always emits `tool.execution.started` before dispatch when execution proceeds.
- Emits `tool.execution.succeeded` on `ExecutionStatus.SUCCEEDED`.
- Emits `tool.execution.failed` on non-success statuses.
- Replay and conflict short-circuit before dispatch (`idempotency.replay` / `idempotency.conflict`).

## Subprocess payload contract

The adapter accepts only these normalized payload fields:

- `argv`: required, non-empty `list[str]`
- `cwd`: optional `str | None`
- `env`: optional `dict[str, str] | None`
- `timeout_ms`: optional `int > 0 | None`

Constraints enforced by `_build_subprocess_request(...)`:

- Unknown payload keys fail validation.
- Missing/invalid `argv` fails validation.
- Invalid `cwd`/`env`/`timeout_ms` types fail validation.
- If payload omits `timeout_ms`, adapter falls back to `invocation.execution.timeout_ms`.

Execution mechanics:

- Uses `subprocess.run(list(argv), shell=False)` semantics (argv list, not shell command string).
- Uses `capture_output=True`, `text=True`, `errors="replace"`, `check=False`.

## Canonical result mapping

| Runtime condition | `status` | `reason_code` |
| --- | --- | --- |
| Protocol is not `ToolProtocol.SUBPROCESS` | `failed` | `tool.unsupported_protocol` |
| Invalid payload shape/fields | `failed` | `tool.invalid_payload` |
| `subprocess.TimeoutExpired` | `failed` | `tool.timeout` |
| `OSError` / launch failure (includes missing executable) | `failed` | `tool.transport_error` |
| Completed process with non-zero exit | `failed` | `tool.execution_failed` |
| Completed process with zero exit | `succeeded` | `None` |

Output payload shape for completed processes:

- `argv`
- `cwd`
- `exit_code`
- `stdout`
- `stderr`

Timeout/transport failures include contextual output fields (`argv`, `cwd`, and timeout/error details).

## Local validation runbook

Run only the contract slice:

```bash
uv run pytest -q \
  tests/infrastructure/test_subprocess_adapter.py \
  tests/tool_contract/core/test_execute_prepared_subprocess_adapter.py \
  tests/tool_contract/writes/test_execute_prepared_tool_invocation.py
```

Or run full suite:

```bash
uv run pytest -q
```

## Troubleshooting and common pitfalls

| Symptom | Likely cause | What to check |
| --- | --- | --- |
| `tool.invalid_payload` | Payload has unsupported key or wrong type | Ensure only `argv/cwd/env/timeout_ms` are present with expected types |
| `tool.transport_error` | Executable path is missing or launch failed | Verify first `argv` entry resolves in runtime environment |
| `tool.timeout` | Command exceeded timeout budget | Check payload `timeout_ms` and `execution.timeout_ms` fallback |
| `tool.execution_failed` | Process ran but returned non-zero exit code | Inspect `exit_code`, `stderr`, and command semantics |

## Known gaps after PR-3

- No HTTP/MCP transport adapters yet.
- No resume bridge from prepared tool drafts into ADR-015/017 continuation flow yet.
- Contract remains internal and protocol-first; public surfaces are unchanged.
