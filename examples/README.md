# Examples & Learning Path

Use these scenarios to introduce Noēsis concepts to engineers, operators, and stakeholders. Each folder keeps real code alongside the immutable artifacts stored under `.noesis/`.

## Quickstart

- `examples/demo.py` – one-file tour that runs two tasks (normal + vetoed) and prints summaries. Pair it with [`docs/explanation/artifacts.mdx`](../docs/explanation/artifacts.mdx) to explain the emitted artifacts.
- `examples/artifacts/state_v1_example.json` – trimmed state snapshot used throughout the docs.

`examples/demo.py` sets `ns.set(runs_dir="./.noesis/episodes/demo")`. That is a **custom `runs_dir`**, not a label subdirectory of the default episodes root. Default runs still land in `.noesis/episodes/ep_<ULID>/`.

## Governance & operations

- `examples/incident_triage/` – LangGraph-based incident loop with Gradio and Streamlit front-ends plus the `ProdGuardPolicy` governor.
- `examples/sql_guard/` – lightweight SQL adapter that shows how to veto destructive statements before the `act` phase.

## Memory & insight

Register a memory port with `context.create_runtime_context()` / `context.register("memory", ...)`. See [`docs/guides/add-memory-port.mdx`](../docs/guides/add-memory-port.mdx).

Inspect `state.json["memory"]` and `summary.json["insight"]["metrics"]` in any demo run to see durable recall and KPI rollups.

## Suggested flow for new contributors

1. Run `uv run python examples/demo.py`.
2. Open the emitted episode under the demo `runs_dir` (look for `ep_*/summary.json` and `state.json`).
3. Step up to `uv run python -m examples.incident_triage.gradio_app` to see governance + dashboards.
4. Customize `context.register("memory", ...)` to plug in domain memories or insight evaluators.
