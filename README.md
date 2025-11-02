# Noēsis (νόησις)

_Understanding, made observable._

Noēsis is a lightweight Python framework for orchestrating, tracing, and improving agentic reasoning workflows.  
It gives every episode a mind-set: contextual awareness, advisory intuition, steerable direction, and measurable insight.

---

> **Public surface (v0.7.1)**
> Stable: `noesis`, `noesis.summary`, `noesis.events`, `noesis.context`, `noesis.learn`, `noesis.episode`, `noesis.io`, `noesis.trace`, `noesis.intuition`, `noesis.direction`, `noesis.insight`, plus the facades under `noesis.runtime.*`.
>
> Prefer the modules-first API (`ns.summary.read`, `ns.events.read`, `noesis.learn.emit`). Reserve `noesis.io.*` for read-only power-user workflows. Avoid importing from `noesis.domain.*`, `noesis.usecases.*`, `noesis.infrastructure.*`, `noesis.interfaces.*`, or modules prefixed with `_` — those remain internal.

---

## ✨ Highlights

- **Observable cognition** – every phase (observe → interpret → plan → act → reflect → learn) emits structured events and summary metrics.
- **Runtime context** – register ports (memory, insight, evaluators) once; inject them per run for deterministic cognition.
- **Direction & intuition** – steer behaviour with advisory policies, interventions, or vetoes that leave auditable traces.
- **Learning feedback** – emit learn artifacts (`learn.emit`) that feed long-term policy stores or analytics pipelines.
- **Guardrails baked in** – public-surface tests, import contracts, and docs keep the API clean and predictable.

---

## 🚀 Quickstart

### Install (uv)

```bash
uv add noesis
noesis run "Summarize this repo"
noesis solve react "Weekly plan for a 3-person team"
noesis events "$(noesis list -j | jq -r '.[0].episode_id')" --phase insight -j
# optional: uv tool install .   # or pipx install .
```

### Python in 30 seconds

```python
import noesis as ns

episode_id = ns.run("Summarize the roadmap", seed=42, intuition=True)
metrics = ns.summary.read(episode_id)["metrics"]
print(metrics["success"])
```

---

## 🧰 Public API in practice

```python
# --- Core happy path ---------------------------------------------------------
import noesis as ns

episode_id = ns.run("Draft weekly update", intuition=False)
metrics = ns.summary.read(episode_id)["metrics"]
print(metrics["success"])

# --- Solving with a custom graph + capturing events --------------------------
from pathlib import Path

# If your runner accepts a callable, pass one; otherwise pass a label/path your loader understands.
episode_id = ns.solve(
    "Generate release notes",
    using=lambda: Path("flows/release_notes.py"),
    intuition=True,
)

for event in ns.events.read(episode_id):
    print(event["phase"], event["payload"])

# --- Working with the runtime context facade ---------------------------------
from noesis import context

ctx = context.create_runtime_context()
ctx.register("memory", provider=my_memory_port, api="memory/1.0")
context.set_context(ctx)

snapshot = context.get_config_snapshot()
print(snapshot)

# --- Finalising summaries in backfills ---------------------------------------
from noesis import summary

summary.finalize(
    run_dir=Path("./runs/demo"),
    episode_id="ep_demo",
    task="Backfill summary",
    seed=0,
    started_at="2025-01-01T00:00:00Z",
    intuition_enabled=False,
    intuition_mode=None,          # or ns.IntuitionMode.ADVISORY
    using_label="core.minimal",
    tags={},
    intuition=None,
    schema_version="1.2.0",
    config=context.get_config_snapshot(),
    ports=ctx.list_ports(),
)

# --- Emitting events outside the orchestrator --------------------------------
run_dir = Path("./runs/manual")
events = ns.events  # module alias
events.start(run_dir, "ep_manual", {"task": "Hand-crafted episode"})
events.ensure(
    run_dir,
    "ep_manual",
    adapter_label="adapter:manual",
    input_excerpt="noop",
    outcome="ok",
)
events.terminate(run_dir, "ep_manual", {"status": "ok"})

# --- Learning helpers (high-level) -------------------------------------------
from noesis import learn

learn.emit(
    run_dir=run_dir,
    episode_id="ep_manual",
    events=list(ns.events.read("ep_manual")),
    metrics=ns.summary.read("ep_manual")["metrics"],
    config=context.get_config_snapshot(),
)

# --- Episode manifest (read-only) --------------------------------------------
from noesis.episode import EpisodeIndex

index = EpisodeIndex("./runs/_episodes", ttl_days=14)
recent = list(index.iter())

# --- Optional: legacy read-only tooling via noesis.io ------------------------
# Prefer ns.summary.read / ns.events.read above; keep io.* for power users.
from noesis.io import list_runs, summary as io_summary, events as io_events

latest = list_runs(limit=1)[0]
details = io_summary(latest["episode_id"])
timeline = list(io_events(latest["episode_id"], stream=True))
```

Prefer the high-level `learn.emit` helper; lower-level builders (`build_learn_payload`, `persist_episode_learning`) remain for migration but will sunset before 1.0.

---

## 📦 Supported modules

| Module | Status | Purpose |
| --- | --- | --- |
| `noesis` | ✅ Stable | Entry points (`run`, `solve`, `set`, `get`) and module facades (`summary`, `events`, `context`, `learn`). |
| `noesis.summary` | ✅ Stable | Read/finalise summaries. |
| `noesis.events` | ✅ Stable | Emit or read cognitive-loop events. |
| `noesis.context` | ✅ Stable | Create/manage runtime contexts and config ports. |
| `noesis.learn` | 🟡 Evolving | Emit learning payloads, persist policy snapshots. |
| `noesis.episode` | ✅ Stable | Read-only episode index API. |
| `noesis.io` | ✅ Stable | Legacy/advanced read-only helpers (keep for analytics tooling). |
| `noesis.runtime.*` | ✅ Stable (facades) | Low-level emitters and summary utilities for power users. |

---

## 🧠 Cognitive loop (at a glance)

| Phase | What happens | Artifact |
| --- | --- | --- |
| Observe | Capture task + context. | `events.jsonl` (`phase="observe"`) |
| Interpret | Translate signals to beliefs. | `events.jsonl` (`phase="interpret"`) |
| Plan | Decide the next actions. | `state.json` (`plan_steps[]`) |
| Act | Execute via adapters/tools. | `events.jsonl` (`phase="act"`) |
| Reflect | Score outcomes, capture reasons. | `summary.json["metrics"]` |
| Learn | Emit learn payloads/persist knowledge. | `learn.jsonl` |

Faculties such as Intuition, Direction, and Insight weave through these phases so every intervention or veto is recorded and testable.

---

## 🧱 Architecture snapshot

- **Context-first** – everything flows through a `RuntimeContext`; ports are versioned and declarative.
- **Clean boundaries** – domain models know nothing about adapters; use cases orchestrate behaviour; infrastructure handles IO.
- **Artifacts, not side effects** – every run produces `events.jsonl`, `summary.json`, `state.json`, and optional `learn.jsonl`.
- **Guardrails** – import-linter contracts, public-surface smoke tests, and docs keep the API tidy.

---

## 🗂️ Project layout

```
noesis/
 ├─ __init__.py           # Public API (run, solve, summary/events/context facades)
 ├─ core.py               # Execution + orchestration
 ├─ config.py             # Global configuration + noesis.toml loader
 ├─ intuition.py          # Advisory layer contracts
 ├─ direction.py          # Interventions + veto helpers
 ├─ insight.py            # Metrics + lightweight analytics
 ├─ io.py                 # Run inspection helpers
 ├─ loader.py             # Dynamic adapter + graph loader
 │
 ├─ adapters/             # Framework bridges (LangGraph, CrewAI, etc.)
 ├─ state/                # Episode state + schema models
 ├─ trace/                # Trace + summary event handling
 └─ exceptions.py         # Framework-specific error types
```

---

## ⚙️ Versioning

- **Package:** noesis v0.7.1  
- **Schema:** summary.schema.json v1.1.0  
- **Python:** ≥ 3.11

All runs embed `schema_version` for reproducibility.

---

## 🪶 License

Apache License 2.0
