# KPI Migration Log

Use this log for any change to KPI formulas, clamps, or weights. Template:

```
- **KPI:** <name>
- **Old behavior:** <brief>
- **New behavior:** <brief>
- **Version:** <X.Y.Z>
- **Impact:** <which dashboards / alerts>
- **Remediation:** <runbook notes>
- **Effective PR:** <link>
- **Reviewers:** <names>
```

## plan_adherence/tool_coverage/veto_count/success — v1.0.0

- **KPI:** Core KPI set
- **Old behavior:** Unpinned formulas and undocumented clamps.
- **New behavior:** Formulas codified in `internal_docs/schema/kpi.v1.yaml` with clamps (0–1) and success weights `{0.35, 0.35, -0.2, 0.5}`.
- **Impact:** Dashboards and regression tests must treat these formulas as source of truth.
- **Remediation:** Regenerate schemas, align KPI regression fixtures, and update docs referencing legacy weights.
- **Effective PR:** _ADR-003 scaffolding (this PR)_
- **Reviewers:** Research & Insight, Core Engineering
