# Direction Layer Overview

Direction lets policies actually steer a run—patch inputs or veto unsafe plans—while preserving full traceability and metrics beyond advisory hints.

Lifecycle (one pass): `advise → log intuition → apply patch / veto → invoke graph → log direction + diff`. If the adapter re-enters (e.g., a streaming graph emits multiple observations), the policy is consulted again at each step boundary.

Noēsis splits *intuition* into two complementary paths:

| Layer | What it does | When it fires | Event phase |
|-------|---------------|---------------|-------------|
| **Advisory** | Hints only (foresight, risk forecasts). | Before execution starts. | `intuition` |
| **Direction** | Interventions + vetoes (light-touch control). | Immediately before handing input to the adapter (and whenever the adapter re-enters). | `direction` |

### Lifecycle

1. **Snapshot** – the adapter collects a minimal state bundle `{"task", "history", "tools_seen", "tags"}`.
2. **Policy consult** – `Intuition.advise(snapshot)` runs. Advisory-only policies return hints; `DirectedIntuition` can ask for interventions or vetoes.
3. **Logging** – the advisory signal is persisted as an `intuition` event. If the policy asked for direction, the adapter evaluates it and appends a `direction` event (with patches, reasons, policy id).
4. **Enforcement** – dict inputs are shallow-merged with the patch (top-level keys overwrite; no deep merge) when `confidence ≥ 0.5`. Vetoes raise `NoesisVeto` before the graph runs and set the forthcoming episode status to `blocked`.
5. **Summary & metrics** – runs record counts and a quick diff:
- `metrics.direction_events`, `direction_applied`, `direction_vetoed`
- `flags.direction = {applied, vetoed, policy, last_diff}`

Where to look:
- **Events** – filter `phase == "direction"` for `{policy, applied, reason, diff}`.
- **Flags** – `summary(ep)["flags"]["direction"]` for `{applied, vetoed, policy, last_diff}`.
- **Metrics** – dashboards can pick up `direction_events`, `direction_applied` (count of applied interventions), `direction_vetoed` (count of vetoes).

### Directive types

```text
DirectiveKind.HINT          # no side effects
DirectiveKind.INTERVENTION  # optional patch (dict merge)
DirectiveKind.VETO          # stop the run via NoesisVeto
```

Reason codes emitted in `direction.payload.reason`:

| Reason | Meaning |
|--------|---------|
| `applied` | Patch merged successfully. |
| `empty_patch` | Policy returned `{}`; run continues unchanged. |
| `policy_low_confidence` | Confidence < 0.5 (skip but log intent). |
| `not_dict_input` | Graph input was not a dict → patch ignored. |
| `veto` | Policy halted execution. |

### Confidence threshold

- Interventions apply when `confidence ≥ 0.5` (configurable via `ns.set(direction_min_confidence=...)`).
- Below the threshold, the adapter logs `policy_low_confidence` and leaves the original input untouched.
- Direction currently patches dict inputs only. Noēsis will wrap bare strings as `{"task": <text>}` by default; provide `__noesis_input_mapper__` or `input_mapper` to emit richer shapes.
- Policy identity in logs appears as `PolicyClass@__version__` when a `__version__` attribute exists, otherwise just `PolicyClass`.

### Troubleshooting

- No diff shown → the patch was empty (`reason: "empty_patch"`).
- Patch ignored → `confidence < 0.5` (`reason: "policy_low_confidence"`).
- Input untouched → graph received a non-dict (`reason: "not_dict_input"`); add `__noesis_input_mapper__`.
- No direction events → intuition disabled (`intuition=False`) or policy returned `None`.
- Veto triggered → direction event logged with `reason: "veto"`, adapter raises `NoesisVeto`, and the episode terminates with status `blocked` in both trace and summary.

### Inspect at a glance

```python
import json, noesis as ns

ep = ns.last()
flags = ns.summary(ep)["flags"]["direction"]
print("Direction:", flags)  # {'applied': 1, 'vetoed': 0, 'policy': 'GuardrailsPolicy@1.0', 'last_diff': ['normalize: false→true']}

events = [e for e in ns.events(ep) if e["phase"] == "direction"]
print(json.dumps(events[-1]["payload"], indent=2) if events else "—")
```

### Where to start

- Read the [How-to guide](howto.md) for a step-by-step tutorial.
- Run the examples:
  - `noesis.examples.city_analysis` for advisory-only policies.
  - `noesis.examples.direction_demo` for interventions, vetoes, and stress tests.

### CI guardrail snippet

```bash
# Fail CI if any nightly guardrail vetoes the run
python - <<'PY'
import noesis as ns, sys
from noesis.examples.direction_demo.policy import GuardrailsPolicy

ep = ns.solve("Nightly QA tasks", using="guardrails", intuition=GuardrailsPolicy())
metrics = ns.summary(ep)["metrics"]
if metrics.get("direction_vetoed", 0) > 0:
    print("Guardrail vetoed nightly run.")
    sys.exit(1)
print("OK: no vetoes.")
PY
```
