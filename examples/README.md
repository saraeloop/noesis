# Examples & Learning Path

Use these scenarios to introduce Noēsis concepts to engineers, operators, and stakeholders. Each folder keeps real code alongside the immutable artifacts stored in `runs/`.

## Quickstart

- `examples/demo.py` – one-file tour that runs two tasks (normal + vetoed) and prints summaries. Pair it with [`runs/README.md`](../runs/README.md) to explain the emitted artifacts.
- `examples/artifacts/state_v1_example.json` – trimmed state snapshot used throughout the README and docs.

## Governance & operations

- `examples/incident_triage/` – LangGraph-based incident loop with Gradio and Streamlit front-ends plus the `ProdGuardPolicy` governor.
- `examples/sql_guard/` – lightweight SQL adapter that shows how to veto destructive statements before the `act` phase.

## Memory & insight

- Start from the [`Runtime context & memory`](../README.md#runtime-context--memory) snippet, then register your own SQLite/FAISS provider with `context.create_runtime_context()`.
- Inspect `state.json["memory"]` and `summary.json["insight"]["metrics"]` in any demo run to see durable recall and KPI rollups.

## MCP & external tools

- Follow the [MCP & external tooling](../README.md#mcp--external-tooling) section to hook existing Model Context Protocol servers into Noēsis.
- Adapters report every tool invocation via `events.jsonl`, so you can share the same observability story whether the tool ran locally, remotely, or inside MCP.

### Suggested flow for new contributors

1. Run `uv run python examples/demo.py`.
2. Open the emitted `runs/demo/<episode>/summary.json` and `state.json`.
3. Step up to `uv run python -m examples.incident_triage.gradio_app` to see governance + dashboards.
4. Customize `context.register("memory", ...)` to plug in domain memories or insight evaluators.
