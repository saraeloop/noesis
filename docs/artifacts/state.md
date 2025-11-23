# State Artifact Guide

Noēsis writes a `state.json` file for every episode inside `runs/<label>/<episode_id>/`. Pair it with `summary.json` and `events.jsonl` to reconstruct what the agent knew, planned, and executed.

## Top-level keys

- `episode`: identifiers, tags, and the adapter/graph that executed the task. Investors usually care about `using` (what ran) and `seed` (for reproducibility).
- `goal`: the natural-language task and any scoped context fed into the run.
- `beliefs`: optional statements the system inferred while interpreting evidence. Each belief includes confidence and provenance so you can audit the source.
- `plan`: planner output with ordered steps. Watch `kind`, `status`, and `depends_on` to quantify decomposition depth and adherence.
- `memory`: facts added to long-term recall plus any scratchpad scribbles. This shows how durable insights accumulate between runs.
- `outcomes`: end-state summary, per-action traces (tool, status, artifacts), and metrics such as `task_score` or custom KPIs.
- `links`: relative pointers to the other immutable artifacts: `events.jsonl`, `summary.json`, `learn.jsonl`.

## KPI callouts

1. **Plan adherence** – count `status="done"` vs total steps and compare to `summary["insight"]["metrics"]["plan_adherence"]`.
2. **Governance pressure** – correlate `outcomes["actions"][*]["result_status"] == "blocked"` with `summary["insight"]["metrics"]["veto_count"]`.
3. **Tool coverage** – number of distinct adapters invoked versus planned `kind="act"` steps.

## Where to look next

- [examples/artifacts/state_v1_example.json](../../examples/artifacts/state_v1_example.json) – canonical demo state pulled into the README.
- [runs/README.md](../runs/README.md) – folder-level primer on how `state.json`, `summary.json`, and `events.jsonl` interlock.
- `noesis view <run_dir>` – CLI visualizer that converts the same JSON into annotated timelines for stakeholder reviews.
