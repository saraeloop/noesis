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
noesis view <episode_id>
# or (works from anywhere):
noesis view .noesis/episodes/<episode_id>
```

If you see “no events matched,” point the viewer to the `.noesis/episodes` folder that holds the episode.

## Tutorials

### 1) Hello Episode — artifacts + phases
- Goal: See the Noēsis cognitive loop and confirm artifacts were written.
- Run:
```bash
uv run python -m tutorials.hello_episode
```
- What you’ll learn:
  - Where artifacts live: `.noesis/episodes/<episode_id>/...`
  - Which phases happened: observe → interpret → plan → governance → act → reflect → learn → terminate → (insight/memory)
  - How to inspect runs: `noesis view <episode_id>`
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

What you’re looking at in `noesis view <episode_id>`:
- Episode — identity + config (planner_mode, intuition, using)
- KPIs — roll-up metrics (what you’ll later gate/alert on)
- Governance — allow/audit/veto decisions (when present)
- Timeline — the event-by-event trace (what happened, in order)

### 2) Guarded LangGraph — governance + guardrails
- Goal: Show how a LangGraph flow can be wrapped with Noēsis governance (allow/audit/veto) and surfaced in the trace.
- Run (after the tutorial is populated):
```bash
uv run python -m tutorials.guarded_langgraph
```
- Expectation: see governance decisions recorded in the timeline and surfaced in `noesis view`, alongside the normal agent phases.

### 3) Trace-Based Evals — quality from traces
- Goal: Demonstrate scoring and evaluating episodes directly from their traces.
- Run (after the tutorial is populated):
```bash
uv run python -m tutorials.trace_based_evals
```
- Expectation: produce an episode whose summary includes evaluation metrics; review them in `noesis view` and in the written artifacts under `.noesis/episodes/<episode_id>/`.
