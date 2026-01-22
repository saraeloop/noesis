# Noēsis Quickstart Tutorials

These tutorials are the fastest way to see Noēsis *in practice*: each run becomes an **episode** with a real **trace** and durable **artifacts** you can inspect.

## Prerequisites
- Python 3.12+
- `uv`
- `OPENAI_API_KEY` in your environment (or `.env`)

## Setup
```bash
cd noesis-quickstart
cp .env.example .env
# edit .env and set OPENAI_API_KEY=...
uv sync
```

## Run any tutorial
All tutorials are runnable modules:
```bash
uv run python -m tutorials.<name>
```

After a run completes, you’ll get an `episode_id`. View it with:
```bash
uv run noesis view <episode_id>
# or (works from anywhere):
uv run noesis view .noesis/episodes/<episode_id>
```

If you see “no events matched,” point the viewer to the `.noesis/episodes` folder that holds the episode.

## Tutorials

### 1) Hello Episode — artifacts + phases
- Goal: See the Noēsis cognitive loop and confirm artifacts + verification were written.
- Run:
```bash
uv run python -m tutorials.hello_episode
```
- What you’ll learn:
  - Where artifacts live: `.noesis/episodes/<episode_id>/...`
  - Which phases happened: observe → interpret → plan → governance → act → reflect → learn → terminate → (insight/memory)
  - How to inspect runs: `uv run noesis view <episode_id>`
  - How verification shows up in `summary.json` when using `workspace` + `verify`
- Expected artifacts:
```
.noesis/episodes/<episode_id>/
  events.jsonl
  state.json
  summary.json
  manifest.json
  prompts.jsonl   # optional (prompt provenance)
```
- What “memory port_missing” means: not an error; this quickstart omits a memory adapter, so persistence is skipped.

What you’re looking at in `uv run noesis view <episode_id>`:
- Episode — identity + config (planner_mode, intuition, using)
- KPIs — roll-up metrics (what you’ll later gate/alert on)
- Governance — allow/audit/veto decisions (when present)
- Timeline — the event-by-event trace (what happened, in order)

### 2) LangGraph Episode — cognition + artifacts
- Goal: Run a LangGraph agent with Noēsis and capture cognitive artifacts.
- Run (after the tutorial is populated):
```bash
uv run python -m tutorials.langgraph_episode
```
- Expectation: cognitive phases + artifacts with verification.

### 3) Governed Side Effects — action candidates + veto
- Goal: Enforce the OS-boundary contract: `action_candidate → governance → act` (or veto).
- Run (after the tutorial is populated):
```bash
uv run python -m tutorials.governed_side_effects
```
- Expectation: unsafe actions are vetoed (no act events) while safe actions succeed.

### 4) Trace-Based Evals — quality from traces
- Goal: Score governed actions directly from their artifacts (`events.jsonl` + `summary.json`; `final.json` when present).
- Run (after the tutorial is populated):
```bash
uv run python -m tutorials.trace_based_evals
```
- Expectation: unsafe actions are vetoed (no act events) while safe actions succeed; scores are derived from `events.jsonl` + `summary.json` (and `final.json` when present).

## Senior Engineer Playbook (why Noēsis)

These are the high-signal, practical things you can do **immediately** with the artifacts.

### 1) Prove behavior with immutable evidence
- **What:** `events.jsonl`, `summary.json`, `state.json`, `final.json` (optional), `manifest.json`
- **Why:** You can audit or diff runs and prove what happened.
- **Do:** `uv run noesis view <episode_id>` then open the files in `.noesis/episodes/<episode_id>/`

### 2) Create CI gates for safety
- **What:** Enforce vetoes for unsafe prompts.
- **Why:** Prevent regressions when models/tools change.
- **Do:** Run `tutorials.trace_based_evals` in CI and fail if any unsafe case is not vetoed.

### 3) Debug regressions with causal chains
- **What:** `caused_by` links across phases in `events.jsonl`.
- **Why:** You can trace **exactly** why an action happened or was blocked.
- **Do:** Grep for `phase="governance"` and follow `caused_by` backward to plan/intent.

### 4) Enforce the side-effect boundary
- **What:** `action_candidate → governance → act` is the contract.
- **Why:** No side effects should occur without a candidate + governance decision.
- **Do:** Assert that any `act` event has a preceding `action_candidate` in the same episode.

### 5) Track product metrics, not just logs
- **What:** `summary.json` and `insight.metrics` expose KPIs.
- **Why:** You can build dashboards and SLOs (success rate, veto count, tool coverage).
- **Do:** Parse `summary.json` into your metrics pipeline.
