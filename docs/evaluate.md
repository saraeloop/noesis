# 🧪 Evaluation Protocol for Noēsis

## Objective
Measure how intuition-guided reasoning affects agentic performance
compared to baseline runs.

---

## A/B Testing Setup

| Group | Description |
|--------|-------------|
| **A (Baseline)** | ReAct or LangGraph agent without intuition. |
| **B (With Intuition)** | Same agent + Noēsis hints enabled. |

Each run should record:
- Task success rate (goal achieved or not)
- Steps taken
- Tool usage correctness
- Chain-of-thought coherence

---

## Seeds & Artifacts
Use fixed seeds for reproducibility and export artifacts as JSON:
- `events.json` – individual step events
- `summary.json` – aggregated episode metrics
- `diff_report.json` – comparison of A/B deltas

---

## Suggested Metrics
- **Δ Success Rate** = (Success_B – Success_A)
- **Δ Steps** = (Steps_A – Steps_B)
- **Δ Tool Correctness** = improvement percentage
- **Δ Termination Quality** = human or LLM-rated confidence