# Schema Migration Log (Artifacts)

Track every versioned change to `summary.json`, `state.json`, `events.jsonl`, and related manifests. Follow the stub:

```
- **Component:** <artifact/field>
- **Old behavior:** <brief>
- **New behavior:** <brief>
- **Version:** <X.Y.Z>
- **Impact:** <who needs to act>
- **Remediation:** <steps or scripts>
- **Effective PR:** <link>
- **Reviewers:** <names>
```

## summary.json — v1.0.0

- **Component:** summary.json
- **Old behavior:** Free-form JSON without `$schema_version`, ungoverned KPI payloads.
- **New behavior:** Canonical schema with required `$schema_version`, deterministic metric fields, and stability flags per ADR-003.
- **Impact:** Analytics consumers must read `$schema_version` and expect normalized KPI fields.
- **Remediation:** Regenerate docs via `python scripts/gen_schema.py`; update any downstream ETL to require `summary.metrics.*`.
- **Effective PR:** _ADR-003 scaffolding (this PR)_
- **Reviewers:** Core Engineering, Product Insights

## state.json — v1.0.0

- **Component:** state.json
- **Old behavior:** Unversioned state blobs with inconsistent planner structures.
- **New behavior:** Versioned schema covering `episode`, `goal`, `plan.steps`, and `links` with explicit stability metadata.
- **Impact:** Replay + diagnostics pipelines must expect the normalized plan array and enforce `$schema_version`.
- **Remediation:** Regenerate schemas; migrate stored fixtures to include top-level `$schema_version`.
- **Effective PR:** _ADR-003 scaffolding (this PR)_
- **Reviewers:** Core Engineering

## events.jsonl — v1.0.0

- **Component:** events.jsonl entries
- **Old behavior:** Append-only JSONL without canonical casing or schema version.
- **New behavior:** Each event now references `schema_version`, enforces ID formats, and documents timing metadata fields.
- **Impact:** Stream processors can validate payloads; governance metrics rely on consistent `phase` enums.
- **Remediation:** Ensure emission pipeline writes `$schema_version` when ADR-003 wiring lands; regen docs for downstream teams.
- **Effective PR:** _ADR-003 scaffolding (this PR)_
- **Reviewers:** Core Engineering, Runtime
