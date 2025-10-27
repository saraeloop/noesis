# 🧠 Noēsis Concepts

## Why Noēsis Exists
Modern agent frameworks like LangGraph and ReAct enable reasoning and tool use,
but they lack *intuition* — the lightweight foresight that helps agents plan,
diagnose, and recover more intelligently.

**Noēsis** (νόησις, Greek for “understanding”) adds an *Intuition Layer* that:
- Forecasts risks in agent decisions (e.g., repeated queries, bad data).
- Provides direction via soft advisory hints.
- Can be turned ON or OFF for controlled A/B comparison.

---

## Design Principles
- **Agnostic Core:** Noēsis can wrap any multi-tool agent system.
- **Advisory, not intrusive:** Intuition never forces actions; it advises.
- **Traceable:** Every intuition event is logged in a schema-compatible record.
- **Composable:** Works as an optional plug-in layer, not a new runtime.

---

## ON/OFF Contract
| Mode | Behavior |
|------|-----------|
| `intuition=False` | Baseline ReAct or LangGraph flow. |
| `intuition=True`  | Adds hint injection, event tracing, and confidence scoring. |

---

## Vision
> “Intuition gives direction.”  
Noēsis provides the missing middle ground between deterministic plans
and stochastic creativity.