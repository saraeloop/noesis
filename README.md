# Noēsis (νόησις)

_Understanding, made observable._

Noēsis is a lightweight Python cognitive framework for orchestrating, tracing, and improving agentic reasoning workflows.  
**TL;DR:** it drops a cognitive loop on top of any agent stack, so every run is observable end-to-end context in, actions out, with advisory Intuition, steerable Direction, and measurable Insight captured as immutable artifacts.

Noēsis works with the graphs, tools, and runtimes you already use. It makes them plan, act, reflect, learn, and remember in a measurable, auditable way.

⸻

## Installation

```bash
# pip
pip install noesis

# uv
uv add noesis

# poetry
poetry add noesis
```

Need the CLI (`noesis run …`, `noesis solve …`)? Install the console script from source with `uv tool install .` or `pipx install .`. Optional pretty-printing for CLI JSON uses `jq` (`brew install jq`).

⸻

## Usage

The simplest way to see Noēsis in action is to run a task and read back the immutable artifacts it produces.

```python
import noesis as ns

# Run a task with cognition enabled
episode_id = ns.run("Draft a weekly engineering update", intuition=True)

# Read back the summary and timeline
summary = ns.summary.read(episode_id)
timeline = list(ns.events.read(episode_id))

print(summary["metrics"]["success"])
for ev in timeline[:5]:
    print(ev["phase"], ev.get("payload"))
```

### Bring your own agent / graph

Noēsis is framework-agnostic. Point `solve()` at your orchestrator (LangGraph, CrewAI, custom Python), and Noēsis will wrap it with planning, reflection, trace events, and summaries.

```python
from pathlib import Path
import noesis as ns

episode_id = ns.solve(
    "Generate release notes from ./CHANGELOG.md",
    using=lambda: Path("flows/release_notes.py"),  # your graph/runner
    intuition=True,
)
```

### Runtime context & memory

Register durable memory or insight evaluators via the context facade; cognition stays explicit and testable.

```python
from noesis import context
from noesis.episode import EpisodeIndex

ctx = context.create_runtime_context()
ctx.register("memory", provider=my_sqlite_memory, api="memory/1.1")  # or FAISS/HNSW
context.set_context(ctx)

index = EpisodeIndex("./runs/_episodes", ttl_days=14)
print(list(index.iter())[:3])
```

`context` is the agent’s scoped worldview (config + registered faculties); pass it explicitly to keep dependencies clear and tests pure.

⸻

## Core capabilities

### Planning & task decomposition

Direction turns vague goals into stepwise plans and keeps them fresh as evidence arrives (observe → interpret → plan). Plans and transitions are written to `events.jsonl` and `state.json`.

### Context & trace management

Every episode emits immutable artifacts:

- `events.jsonl` – timeline of phases (observe/interpret/plan/act/reflect/learn) with causal IDs
- `summary.json` – metrics, outcomes, and cross-links
- `state.json` – current plan and episode state

### Long-term memory

Plug in a memory port (SQLite for dev, FAISS/HNSW for semantic recall). After each summary, Noēsis persists normalized facts and episode links so future runs can retrieve relevant context.

### Reflection & learning

Noēsis records reflections and can emit learning payloads for policy updates or offline analysis.

```python
from pathlib import Path
from noesis import learn, events, summary, context

run_dir = Path("./runs/demo")
episode_id = "ep_demo"

learn.emit(
    run_dir=run_dir,
    episode_id=episode_id,
    events=list(events.read(episode_id)),
    metrics=summary.read(episode_id)["metrics"],
    config=context.get_config_snapshot(),
)
```

Use these artifacts to tune prompts, policies, or evaluators—or wire them into a governance loop.

### Governance & insight

Pre-act governance policies can audit or veto actions before the `act` phase when the planner mode is `meta` (default). On veto, the ACT phase is logged as `outcome="blocked"` and no tool invocation occurs. Direction events reflect both heuristic directives and governance verdicts, and summaries expose versioned per-episode insight metrics under `summary["insight"]["metrics"]`.

```python
import os
import noesis as ns

# meta planner + PreActGovernor is the default
episode_id = ns.run("Draft a rollout plan for the new release")

# opt out of governance by switching planner mode
ns.set(planner_mode="minimal")
legacy_episode = ns.run("Draft a rollout plan for the new release")

# restore the meta planner (or set NOESIS_PLANNER=meta in the environment)
ns.set(planner_mode="meta")
```

### Demo: meta vs minimal runs

```python
import noesis as ns

ns.set(runs_dir="./runs/demo")

eid_meta = ns.run("Summarize the release notes in ./CHANGELOG.md", intuition=False)
eid_veto = ns.run("Danger operation: delete production database", intuition=False)

for eid in (eid_meta, eid_veto):
    summary = ns.summary.read(eid)
    insight = summary["insight"]["metrics"]
    print(
        f"{eid}: success={summary['metrics']['success']} "
        f"vetoes={insight['veto_count']} "
        f"plan_adherence={insight['plan_adherence']:.4f} "
        f"tool_coverage={insight['tool_coverage']}"
    )
```

Typical output:

```
ep_20251103_181813_293036_f3da_s0: success=True vetoes=0 plan_adherence=1.0000 tool_coverage=1.0
ep_20251103_181813_294994_1d16_s0: success=False vetoes=1 plan_adherence=0.3333 tool_coverage=0.0
```

### Human-in-the-loop & governance (optional)

Add pre-plan or pre-act hooks to require approval or veto risky actions. Noēsis logs `governance.audit` / `governance.veto` events so trust is measurable.

⸻

## Customizing Noēsis

You can tailor cognition without committing to a specific runtime or library.

### Model / planner

Noēsis is model-agnostic—keep whichever LLM or policy your graph already uses. Noēsis decorates execution with the cognitive loop and artifacts; it does not replace your model choice. Planner mode is configurable via `NOESIS_PLANNER=meta|minimal` (or `ns.set(planner_mode=\"...\")`) so you can opt into the depth-limited meta planner and governance gate when ready.

### “System prompt”

Rather than one mega prompt, Noēsis splits responsibilities:

- **Intuition** – advisory heuristics (LLM or rule-based) for interpretation
- **Direction** – planner + strategy reflection (Tree-of-Thought-style branching optional)
- **Insight** – metrics/evaluations that feed summaries and learning

Keep your graph’s prompts; add faculty-specific guidance when helpful.

### Tools

Your tools remain your tools. Noēsis observes tool calls via `act` events and can route outcomes into memory and reflection automatically.

### Faculties & hooks (middleware analogy)

Think of faculties like modular middleware:

- **Intuition**: advisory reasoning
- **Direction**: planning, adjustment, veto integration
- **Insight**: evaluation/metrics roll-up
- **Governance (optional)**: enforce policies with auditable vetoes

⸻

## Sub-agents & complex workflows

Noēsis doesn’t force a sub-agent API—it embraces your existing one. If a LangGraph/CrewAI/OpenDevin workflow spawns subordinate agents, Noēsis traces them and persists their outcomes like any other steps:

- Keep the isolation semantics from your framework.
- Measure plan changes, action latency, success ratios, and long-term recall hits via Noēsis artifacts.

⸻

## MCP & external tooling

Adapters let Noēsis index and observe actions from MCP servers (Anthropic’s Model Context Protocol). You can keep tool execution external and safe while still capturing causal timelines and summary metrics inside `runs/`.

⸻

## Sync vs async

Use the same `run` / `solve` API. If your orchestrator is async, expose it via `using=` (callable or path) and Noēsis wraps timing, events, and summaries around it.

⸻

## What Noēsis adds (at a glance)

- A real plan (Direction) instead of ad-hoc action loops
- Traces & metrics you can trust (`events.jsonl`, `summary.json`, `state.json`)
- Memory that matters (SQLite/FAISS) for cross-episode recall
- Learning signals for improving policies/prompts over time
- Framework freedom—LangGraph, CrewAI, OpenDevin, custom runners… all welcome

⸻

## API cheatsheet

```python
from pathlib import Path
import noesis as ns
from noesis import context, summary, events, learn
from noesis.episode import EpisodeIndex

# Run / Solve
eid = ns.run("Summarize this repo", intuition=True)
eid = ns.solve("Release notes", using=lambda: Path("flows/release_notes.py"))

# Artifacts
summary.read(eid)
list(events.read(eid))

# Emit extra events (optional)
run_dir = Path("./runs/manual")
events.start(run_dir, "ep_manual", {"task": "demo"})
events.ensure(run_dir, "ep_manual", adapter_label="grep", input_excerpt="...", outcome="ok")
events.terminate(run_dir, "ep_manual", {"status": "ok"})

# Context & memory
ctx = context.create_runtime_context()
ctx.register("memory", provider=my_sqlite_memory, api="memory/1.1")
context.set_context(ctx)

# Learning
learn.emit(
    run_dir=run_dir,
    episode_id="ep_manual",
    events=list(events.read("ep_manual")),
    metrics=summary.read("ep_manual")["metrics"],
    config=context.get_config_snapshot(),
)

# Episode index
index = EpisodeIndex("./runs/_episodes", ttl_days=14)
list(index.iter())
```

⸻

## Stability & versioning

- Public modules to rely on today: `noesis`, `noesis.summary`, `noesis.events`, `noesis.context`, `noesis.learn`, `noesis.episode`, `noesis.io`, `noesis.trace`, plus the facades under `noesis.runtime.*`.
- Evolving modules slated to stabilize post-0.7: `noesis.learn`, `noesis.insight`, and advanced helpers inside those packages.
- Avoid importing from `noesis.domain.*`, `noesis.usecases.*`, `noesis.infrastructure.*`, `noesis.interfaces.*`, or underscore-prefixed modules—they remain internal.
- Need the full matrix? See **API Surface & Stability** in the docs.

Version details:

- **Package:** noesis **v0.8.0**
- **Schema:** summary.schema.json **v1.1.0**
- **Python:** **≥ 3.11**

⸻

## Acknowledgements

Inspired by the research and practice behind ReAct (Yao et al., 2022), Reflexion (Shinn et al., 2023), Tree-of-Thoughts (Yao et al., 2023), Voyager (Wang et al., 2023), and Meta-CoT (Zhang et al., 2024), as well as production systems such as Claude Code and Deep Research (Anthropic PBC).

## License

Apache 2.0
