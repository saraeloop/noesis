# Direction Layer Demo

Showcases the Noēsis direction layer:

1. Baseline run skips data normalization → graph emits a warning.
2. Directed run applies an intuition intervention (`normalize=True`) before execution and logs a `direction` event with a diff.
3. Risky task (“exfiltrate…”) is vetoed, raising `NoesisVeto` and recording a blocked `direction` event.
4. Stress tests cover edge cases: empty patches, low confidence, multi-key patches, and non-dict inputs. Each prints the normalized reason string (`empty_patch`, `policy_low_confidence`, `not_dict_input`, etc.).
5. Confidence threshold is currently fixed at ≥0.5; the low-confidence test shows how directives fall back cleanly until you opt into a different cutoff.

Run it:

```bash
uv run python -m noesis.examples.direction_demo.direction_demo
```

Inspect logs afterwards:

```python
import noesis as ns, json
ep = ns.last()
summary = ns.summary(ep)
print(summary["flags"]["direction"])  # {'applied': ..., 'vetoed': ..., 'last_diff': [...]}
print(json.dumps(summary["metrics"], indent=2))
print([e for e in ns.events(ep) if e["phase"] == "direction"])  # includes diff + policy tag
```
