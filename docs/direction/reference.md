# Direction Layer Reference

Quick lookup for policies, events, and metrics.

## Policy surface

```python
class MyPolicy(noesis.DirectedIntuition):
    __version__ = "1.0"

    def advise(self, state):
        return self.intervene(
            advice="Normalize inputs",
            patch={"normalize": True},
            confidence=0.7,
            rationale="Ensure apples-to-apples",
        )
```

- `DirectedIntuition.hint(...)` – hints only (no patches).
- `DirectedIntuition.intervene(...)` – proposes a shallow dict merge.
- `DirectedIntuition.veto(...)` – stops execution via `noesis.NoesisVeto`.
- Policy identity in logs is `PolicyClass@__version__` (or just `PolicyClass` if no version attribute).

## Event phases

| Phase | Emits | Notes |
|-------|-------|-------|
| `start` | runner | Core metadata (task, seed, adapter label). |
| `intuition` | policy | Advisory hints (always safe). |
| `direction` | adapter | Applied/vetoed directives with diff + reason. |
| `reason` / `observe` / `terminate` | adapter/core | Existing LangGraph lifecycle events. |

## Direction payload

```json
{
  "kind": "intervention",
  "policy": "GuardrailsPolicy@1.0",
  "applied": true,
  "reason": "applied",
  "patch": {"normalize": true},
  "diff": [{"key": "normalize", "before": false, "after": true}]
}
```

Reason codes:

| `reason` | Meaning |
|----------|---------|
| `applied` | Patch merged successfully. |
| `empty_patch` | Policy returned `{}`. |
| `policy_low_confidence` | Confidence < 0.5 (current threshold). |
| `not_dict_input` | Graph input not a dict; mapper missing. |
| `veto` | Policy halted the run (`NoesisVeto`, status `blocked`). |

Merge semantics: dict merge is shallow; patched keys overwrite existing keys, nested structures are replaced wholesale.

## Summary + metrics

`summary(ep)["flags"]["direction"]` → `{applied, vetoed, policy, last_diff, threshold}`.

`summary(ep)["metrics"]` adds:

- `direction_events` – number of `direction` events logged.
- `direction_applied` – count of interventions with `applied=True`.
- `direction_vetoed` – count of veto events.

`events(ep)` – filter `phase == "direction"` to inspect full payloads.

## Exceptions

- `noesis.NoesisVeto` – raised whenever a policy vetoes (`reason: "veto"`). The episode terminates with status `blocked` and the message is recorded in `terminate`.

## Defaults and limits

- Confidence threshold for applying patches: default `0.5`, configurable via `ns.set(direction_min_confidence=...)`.
- Direction operates on dict inputs only—supply `__noesis_input_mapper__` for custom schemas.
- Multiple policies must be composed manually (e.g., orchestrate inside one `advise`); the last returned directive wins.
