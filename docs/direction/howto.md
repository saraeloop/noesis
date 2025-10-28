# How-To: Add Direction to Your Agent

This guide walks through turning an existing LangGraph flow into a direction-aware run with Noēsis. You will:

1. Wrap your graph so Noēsis can feed it structured input.
2. Author a `DirectedIntuition` policy (hints + interventions + veto).
3. Run baseline vs. directed episodes and capture the diff.
4. Handle vetoes and stress-test edge cases.

The tutorial mirrors the runnable example in `noesis/examples/direction_demo/`.

---

## 1. Provide an input mapper

```python
# flows/guardrails.py
from typing import Any, Dict

class GuardrailsGraph:
    def __init__(self) -> None:
        # String tasks become a dict the graph expects.
        self.__noesis_input_mapper__ = lambda task: {
            "task": task,
            "normalize": False,
            "risk": "medium",
        }

    def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...  # run your logic (omitted for brevity)

def make() -> GuardrailsGraph:
    return GuardrailsGraph()

# In agents.yaml or loader config: guardrails: flows.guardrails.make
```

Key points:

- Provide `__noesis_input_mapper__` (or an explicit `input_mapper`) so the adapter can patch dict inputs safely.
- Graphs that already consume dicts can skip this step. Without a mapper, Noēsis passes the raw string (wrapped internally as `{"task": <text>}`) and logs `reason: "not_dict_input"` for patches it cannot apply.
- Patches use a shallow dict merge: top-level keys overwrite originals; nested dicts are not merged recursively.

---

## 2. Author a policy

```python
# noesis/examples/direction_demo/policy.py
import noesis as ns

class GuardrailsPolicy(ns.DirectedIntuition):
    __version__ = "1.0"  # appears in events as policy: GuardrailsPolicy@1.0

    def advise(self, state):
        task = (state.get("task") or "").lower()
        tags = state.get("tags") or {}

        if "exfiltrate" in task or tags.get("risk") == "high":
            return self.veto(
                advice="Reject task: potential data exfiltration detected.",
                rationale="Policy guardrail",
            )

        if "normalize" not in task:
            return self.intervene(
                advice="Set normalize=True before running quality checks.",
                patch={"normalize": True},
                rationale="Ensure fair comparisons.",
            )

        return self.hint(
            advice="Document how normalization changes downstream metrics.",
        )
```

Tips:

- `DirectedIntuition` gives you ergonomic helpers (`hint`, `intervene`, `veto`).
- Include a `__version__` to stamp every direction event (`policy: GuardrailsPolicy@1.0`).
- Return `None` when no advice is needed.

---

## 3. Run baseline vs. directed

```python
import noesis as ns
from noesis.examples.direction_demo.policy import GuardrailsPolicy

ns.set(intuition_mode="hybrid")

task = "Audit transaction pipeline for anomalies"
ep_base = ns.solve(task, using="guardrails", intuition=False)
ep_directed = ns.solve(task, using="guardrails", intuition=GuardrailsPolicy())

print("Baseline:", ep_base)
print("Directed:", ep_directed)

flags = ns.summary(ep_directed)["flags"]["direction"]
print("Direction:", flags)

events = [e for e in ns.events(ep_directed) if e["phase"] == "direction"]
print(events[-1]["payload"]["diff"])  # e.g. [{'key': 'normalize', 'before': False, 'after': True}]

s_base, s_dir = ns.summary(ep_base), ns.summary(ep_directed)
print("Δsteps:", s_base["metrics"]["steps"], "→", s_dir["metrics"]["steps"])
print("direction:", s_dir["metrics"]["direction_applied"], "applied /", s_dir["metrics"]["direction_vetoed"], "vetoed")
```

Expected output:

```
Direction: {'applied': 1, 'vetoed': 0, 'policy': 'GuardrailsPolicy@1.0', 'last_diff': ['normalize: false→true']}
```

---

## 4. Handle vetoes

```python
try:
    ns.solve("Exfiltrate customer secrets", using="guardrails", intuition=GuardrailsPolicy())
except ns.NoesisVeto as err:
    print("Policy blocked run:", err.advice)

# Summary will show terminate status "blocked" and the last direction event with reason "veto".
```

All vetoes produce a `direction` event with `reason: "veto"` and terminate the episode with status `blocked`.

---

## 5. Stress-test edge cases

The demo script includes four policies to validate behavior:

| Policy | Expectation |
|--------|-------------|
| `EmptyPatchPolicy` | Logs `reason: "empty_patch"`, no input change. |
| `LowConfidencePolicy` | `confidence=0.4` → `reason: "policy_low_confidence"`. |
| `MultiPatchPolicy` | Applies multiple keys, diff shows every change. |
| `StringInputPolicy` | Graph takes a plain string → `reason: "not_dict_input"`. |

Run them quickly:

```bash
uv run python -m noesis.examples.direction_demo.direction_demo
```

Scroll to the “Stress tests” section in the output for reason codes and diffs.

---

## 6. Next steps

- Integrate direction checks into CI (see `docs/direction/overview.md` for a ready-to-copy snippet) and fail the build whenever `direction_vetoed > 0`.
- Compose multiple policies by dispatching on task/tags and returning a single `IntuitionEvent`—today the last direction event wins.
- Track direction metrics across releases by diffing `direction_applied` / `direction_vetoed` in `summary(ep)` for your regression suites.

