# Noēsis (νόησις) — Greek for “understanding” or “intellect”

Naosis is a lightweight Python framework for running, tracing, and evaluating agentic reasoning workflows.
It extends LangGraph-style execution with an Intuition Layer that provides hint-based foresight and risk forecasting for multi-tool agents.

---

## 🚀 Quickstart (local dev with uv)

```bash
git clone https://github.com/yourname/naosis.git
cd naosis
uv sync
```

Then run your first episode:

```python
import naosis as ns

ep = ns.run(task="lit_synth", seed=42, intuition=True)
ns.summary(ep)
ns.metrics(ep)
```

Outputs are written to:

```
runs/<episode_id>/
 ├─ events.jsonl   # step-by-step trace
 └─ summary.json   # metrics, hints, forecasts, results
```

---

## 🧩 API at a Glance

```python
import naosis as ns

ep   = ns.run(task="demo", seed=0, intuition=True)
summ = ns.summary(ep)
evts = ns.events(ep)
mets = ns.metrics(ep)

ns.set(runs_dir="./runs", agents="agents.yaml")
eps  = ns.list(limit=10)
last = ns.last()
```

| Function | Description |
|----------|-------------|
| `run()` | Execute one agent episode |
| `summary()` | Load summary JSON |
| `events()` | Load or stream events |
| `metrics()` | Return summary metrics |
| `list()` | List prior runs |
| `last()` | Get last run ID |
| `set()` | Global config overrides |
| `paths()` | Return file paths for a run |

---

## 🧠 Intuition Layer

When `intuition=True`, agents receive pre-run hints and risk forecasts derived from previous runs.
Toggle this flag to compare baseline vs. intuition-guided reasoning in your experiments.

---

## 🧾 Project Layout

```
noesis/     # library source
schemas/    # JSON Schemas for trace/summary
tests/      # unit tests
examples/   # minimal usage docs
```

---

## ⚙️ Versioning

- **Package**: naosis 0.1.0 (SemVer)
- **Schema**: summary.schema.json v1.0.0
- **Python**: ≥ 3.11

All episode outputs include `schema_version` for reproducibility.

---

## 🪶 License

Apache License 2.0
