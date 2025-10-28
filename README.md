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
| Metis | `adapters/metis.py` | 🔜 Planned |

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

- **Package:** noesis v0.1.0
- **Schema:** summary.schema.json v1.0.0
- **Python:** ≥ 3.11

All runs embed a `schema_version` field for reproducibility and auditability.

---

## 🪶 License

Apache License 2.0
