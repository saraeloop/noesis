🧪 Noēsis Examples

Runnable, minimal examples that show how to use Noēsis — a framework for intuition-guided agentic reasoning.
Each example lives in its own folder with scripts, data, and documentation.

```
examples/
├── city_analysis/             # advisory hints vs baseline
│   ├── city_analysis.py
│   ├── city.py
│   ├── data/
│   │   └── cities.csv
│   └── README.md
└── direction_demo/            # interventions + veto (direction layer)
    ├── direction_demo.py
    ├── policy.py
    └── README.md
```

**Coming soon:**
- `basic_run.py` - Smallest possible episode (no adapter)
- `langgraph_react.py` - LangGraph integration
- `batch_eval.py` - Batch comparison (intuition on/off)

⸻

🚀 Running examples

From the repository root:

```bash
uv sync
uv run python -m noesis.examples.city_analysis.city_analysis
uv run python -m noesis.examples.direction_demo.direction_demo
```

Always use the `-m noesis.examples...` form — it keeps imports consistent across environments.

⸻

🧩 What you'll learn

| Example | Focus | Key API |
|---------|-------|---------|
| city_analysis | Real data + advisory hints | `ns.solve()` + custom `CityIntuition` |
| direction_demo | Direction layer (intervene / veto + stress tests) | `ns.solve()` + `DirectedIntuition` |


⸻

🧠 About City Analysis

Folder: `examples/city_analysis/`

**Files:**

| File | Purpose |
|------|---------|
| `city_analysis.py` | main script comparing Tokyo vs Kyoto |
| `city.py` | defines `CityIntuition` – a heuristic advisor |
| `data/cities.csv` | dataset (population, GDP, traits) |
| `README.md` | explanation and interpretation of results |

Run it:

```bash
uv run python -m noesis.examples.city_analysis.city_analysis
```

Example output:

```
Δ Steps: 4 → 6
Δ Coherence: 0.0 → 0.0
Δ Intuition Events: 2
```

**Interpretation** (from the sub-README):

Enabling `CityIntuition` adds pre-run advisory events — more "thought moments."  
Δ Steps ≈ cognitive expansion → the agent reflected more before acting.

⸻

🧭 About Direction Demo

Folder: `examples/direction_demo/`

**Highlights:**

- Shows how `DirectedIntuition` patches input (`normalize=True`) before the `guardrails` flow runs.
- Emits `direction` events with diffs; summary metrics expose `direction_events`, `direction_applied`, `direction_vetoed`.
- Demonstrates typed veto handling via `NoesisVeto` for prohibited tasks.

Run it:

```bash
uv run python -m noesis.examples.direction_demo.direction_demo
```

Inspect the last run:

```python
import noesis as ns, json
ep = ns.last()
print(json.dumps(ns.summary(ep)["metrics"], indent=2))
print([e for e in ns.events(ep) if e["phase"] == "direction"])
```

⸻

🧩 Adding your own example

1. Create a new folder under `examples/`:

```
examples/my_project/
├── my_project.py
├── data/...
└── README.md
```

2. Make it runnable as a module:

```bash
uv run python -m noesis.examples.my_project.my_project
```

3. Use `ns.run()` or `ns.solve()` as needed.
4. Document any metrics or intuition logic inside its `README.md`.

⸻

🧾 Outputs

All examples write results to:

```
runs/<episode_id>/
 ├─ events.jsonl   # chronological trace
 └─ summary.json   # flags, metrics, answers
```

Inspect quickly:

```bash
uv run python - <<'PY'
import noesis as ns, json
ep = ns.last()
print(json.dumps(ns.summary(ep), indent=2)[:600], "...")
PY
```
