# Noēsis (νόησις)

_"understanding" / "intellect"_

Noēsis is a lightweight Python framework for running, tracing, and evaluating agentic reasoning workflows.
It extends LangGraph-style execution with an Intuition Layer for hint-based foresight, risk forecasting, and outcome analysis.

---

## 🚀 Quickstart (uv)

```bash
git clone https://github.com/yourname/noesis.git
cd noesis
uv sync
```

Run your first episode:

```python
import noesis as ns

ep = ns.run(task="Summarize", seed=42, intuition=True)
ns.summary(ep)
ns.metrics(ep)
```

Outputs:

```
runs/<episode_id>/
 ├─ events.jsonl   # step-by-step trace
 └─ summary.json   # metrics, hints, forecasts, results
```

---

## 🧩 Hello, World (LangGraph)

Folder name is flexible — `flows/`, `graphs/`, or `agents/` all work.

**flows/react.py**

```python
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage
from typing import TypedDict

class State(TypedDict):
    task: str
    response: str

def make():
    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o-mini")
    
    def process_task(state: State) -> State:
        response = llm.invoke([HumanMessage(content=f"Compare {state['task']}")])
        return {"response": response.content}
    
    g = StateGraph(State)
    g.add_node("start", process_task)
    g.set_entry_point("start")
    g.set_finish_point("start")
    return g.compile()
```

Run it through Noēsis — no registration required:

```python
import noesis as ns

ep = ns.solve("Compare two cities", using="react", intuition=True)
ns.summary(ep)
```

---

## 🧩 API at a Glance

```python
import noesis as ns

ep   = ns.run(task="demo", seed=0, intuition=True)     # baseline (no adapter)
summ = ns.summary(ep)
evts = ns.events(ep)
mets = ns.metrics(ep)

ns.set(runs_dir="./runs", agents="agents.yaml")
eps  = ns.list(limit=10)
last = ns.last()
```

| Function | Description |
|----------|-------------|
| `run()` | Execute one episode (baseline) |
| `solve()` | Run using an external adapter (e.g. LangGraph) |
| `summary()` | Load summary JSON |
| `events()` | Load or stream events |
| `metrics()` | Return computed metrics |
| `list()` | List prior runs |
| `last()` | Get most recent run ID |
| `set()` | Override global config |
| `paths()` | Return canonical file paths |

---

## 🧠 Intuition Layer

When `intuition=True`, Noēsis injects pre-run advisory hints and risk forecasts derived from prior episodes.
This enables controlled comparisons between baseline vs. intuition-guided reasoning — essentially, memory for foresight.

### 🧭 Direction Layer (intuition with steering)

**Author a policy (hint / intervene / veto)**

```python
import noesis as ns

class Guardrails(ns.DirectedIntuition):
    def advise(self, state):
        task = state["task"].lower()
        if "compare" in task and "gdp" in task:
            return self.intervene(
                advice="Normalize city metrics before comparing.",
                patch={"normalize": True},
                rationale="Enforce apples-to-apples comparisons.",
            )
        if "leak" in task:
            return self.veto(
                advice="Stop: policy prohibits data exfiltration steps.",
                rationale="Policy compliance",
            )
        return self.hint(advice="Call out culture alongside economics.")
```

**Run (direction ON by default when a policy is supplied).**

```python
episode_id = ns.solve("Compare Tokyo and Kyoto GDP", using="react", intuition=Guardrails())
```

For engineers: patches are applied before graph invocation, so you can enforce preconditions (e.g., `normalize=True`) without changing your graph code. Every intervention is logged with a diff, so you can A/B and roll back cleanly.

Example script: `uv run python -m noesis.examples.direction_demo.direction_demo`

**Under the hood:**
- Snapshot state (task, tags, rolling history, tools) and hand it to the policy.
- Log the advisory signal and, if present, the resulting direction event with target/scope metadata.
- Apply the shallow patch to dict inputs (diff logged) or skip with a reason if unsupported.
- Veto raises `NoesisVeto`, ending the episode with a `direction` event marked `status='blocked'`.

**Inspect: summary, metrics, events.**

```python
summ = ns.summary(episode_id)
summ["metrics"]["direction_events"]   # total direction signals
summ["metrics"]["direction_applied"]  # patches merged successfully
summ["metrics"]["direction_vetoed"]   # runs blocked by policy
events = ns.events(episode_id)
[e for e in events if e["phase"] == "direction"]
```

Typical outcomes: `+1–2` `direction_events`, `direction_applied=1`, and an extra `direction` line in `events.jsonl` showing `{target:'input', scope:'episode', applied:true, patch:{normalize:True}}`.

Patches are shallow-merged into dict inputs (no deep merge); string tasks are mapped via the adapter’s input mapper first. If the graph expects non-dict inputs and you skip an input mapper, the patch is ignored but still logged.

Edge cases: if multiple policies emit patches, the last event you return wins, and every attempt is logged. Veto raises a typed `NoesisVeto`, so you can catch policy stops separately from runtime failures. A future `direction_helped` metric can compare paired runs to flag whether steering improved outcomes.

Dashboards: `summary(...)["flags"]["direction"]` reports `{applied, vetoed}` so you don’t have to recompute counts. Every direction payload is stamped with the policy name/version plus a normalized reason (`applied`, `empty_patch`, `not_dict_input`, `policy_low_confidence`, `veto`).

Confidence threshold: interventions apply when `confidence ≥ 0.5`. Below that, they log `policy_low_confidence` and leave the graph input untouched. Adjust it at runtime with `ns.set(direction_min_confidence=0.6)`.

Quick peek pattern (copy/paste ready):

```python
import json, noesis as ns
ep = ns.last()
flags = ns.summary(ep)["flags"]["direction"]
print("Direction:", flags)
events = [e for e in ns.events(ep) if e["phase"] == "direction"]
print(json.dumps(events[-1]["payload"], indent=2) if events else "—")
```

`flags["direction"]["last_diff"]` gives you a human-friendly glimpse, e.g. `['normalize: false→true']`. The same block also reports the active threshold (`threshold` field).

Further reading:
- [Direction overview](docs/direction/overview.md) – lifecycle, troubleshooting, CI guardrails.
- [Direction how-to](docs/direction/howto.md) – step-by-step tutorial with code.
- [Direction reference](docs/direction/reference.md) – reason codes, metrics, API cheatsheet.

### 🛠️ CLI shortcuts

Install the package (or run via `uv run`) and use the bundled CLI for quick checks:

```bash
noesis run "Summarize the weekly report"
noesis solve "Audit transaction pipeline" --using guardrails --policy noesis.examples.direction_demo.policy:GuardrailsPolicy
noesis list-runs --limit 5
noesis show ep_20250101_120000_dead_beef_s0
noesis events ep_20250101_120000_dead_beef_s0 --phase direction
```

### ⚙️ Configuration

Create a `noesis.toml` (or `.noesis.toml`) in your project root to share defaults between CLI and Python:

```toml
runs_dir = "runs"
direction_min_confidence = 0.6
# intuition_mode = "hybrid"
```

---

## 🔌 Adapter Model

Noēsis delegates execution to lightweight adapters that bridge external frameworks.
Each adapter implements a shared Executor protocol, ensuring unified tracing and intuition across frameworks.

```python
ep = ns.solve("Compare two cities", using="react")
# Loader resolves "react" → loads flows/react.py
# LangGraphAdapter executes graph.run(task)
# Noēsis logs all trace + intuition events
```

| Framework | Adapter path | Status |
|-----------|--------------|--------|
| LangGraph | `adapters/langgraph.py` | ✅ Implemented |
| CrewAI | `adapters/crewai.py` | 🔜 Planned |
| AutoGen | `adapters/autogen.py` | 🔜 Planned |

Adapters make Noēsis framework-agnostic and future-proof.

---

## 🗂️ Project Layout

```
noesis/
 ├─ __init__.py           # Public API (run, solve, summary, etc.)
 ├─ core.py               # Execution + orchestration
 ├─ io.py                 # I/O helpers
 ├─ loader.py             # Dynamic adapter + graph loader
 │
 ├─ adapters/             # Framework bridges (LangGraph, CrewAI, etc.)
 │   └─ langgraph.py
 ├─ eval/                 # Evaluation + metrics
 │   └─ metrics.py
 ├─ intuition/            # Intuition layer (foresight logic)
 │   └─ base.py
 ├─ state/                # Episode state + schema models
 │   └─ episode.py
 ├─ trace/                # Trace + summary event handling
 │   └─ files.py
 └─ config.py             # Global configuration
```

---

## ⚙️ Versioning

- **Package:** noesis v0.1.0-alpha
- **Schema:** summary.schema.json v1.0.0
- **Python:** ≥ 3.11

All runs embed a `schema_version` field for reproducibility and auditability.

---

## 🪶 License

Apache License 2.0
