# City Analysis — Intuition-Guided Comparison Example

This example demonstrates how **Noēsis** models “cognitive expansion” when an intuition layer is active.

## 📋 Overview

Two cities (Tokyo and Kyoto) are compared using population, GDP per capita, and cultural traits.  
The same reasoning workflow is executed twice:

1. **Baseline** — no intuition guidance (`intuition=False`)  
2. **Intuition-Guided** — custom `CityIntuition()` provides pre-run hints

```bash
uv run python -m noesis.examples.city_analysis

Example output:

Baseline: ep_20251028_182710_s0
Intuition-guided: ep_20251028_182710_s1

Δ Steps: 4 → 6
Δ Coherence: 0.0 → 0.0
Δ Intuition Events: 2


⸻

🧩 Interpretation

The baseline execution produced 4 steps — just the system-level lifecycle (start, observe, terminate).
With CityIntuition, Noēsis logged 2 additional intuition phases, increasing total steps to 6.

This means the reasoning trace became richer:
Intuition injected pre-run advisory hints (“normalize GDP and population”), representing additional thought moments.

Δ Steps ≈ cognitive expansion
The agent didn’t do more actions, but the system recorded more reflection.

⸻

🚦 What It Demonstrates

Metric	Description	Meaning Here
steps	total logged reasoning events	↑ from 4 to 6
intuition_events	hints or foresight from advisor	2 events
coherence	(placeholder metric) internal consistency	unchanged


⸻

💡 Files

examples/
├── city_analysis.py        ← main runnable script
├── city.py                 ← defines CityIntuition
├── data/
│   └── cities.csv          ← dataset
└── city_analysis.md        ← documentation / explanation


⸻

✅ Summary:
This example is the first demonstration that activating intuition changes the cognitive structure of reasoning — measurable through step count and event trace.
It’s a minimal benchmark of reflectivity vs. reactivity in Noēsis.

⸻

That’s how LangGraph, Hugging Face, and others structure it:
	•	one focused README per scenario (clear “why” and “what happened”),
	•	short index README listing all demos,
	•	and never mixing multiple patterns in one explanation.

Would you like me to rewrite your examples/README.md into that index-style overview, so this new city_analysis.md fits cleanly beneath it?