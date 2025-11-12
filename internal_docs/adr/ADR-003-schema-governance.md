# ADR-003 — Schema Governance & KPIs

- **Status:** Accepted
- **Date:** 2025-11-11
- **Owner:** Sara Loera (saraeloop)
- **Reviewers:** Data Platform, Core Engineering, Product Insights
- **Related roadmap items:** Phase 0 “Road to v1.0.0”, ADR-001, ADR-002

---

## 1. Context

Episode artifacts (`summary.json`, `state.json`, `events.jsonl`, `learn.jsonl`, manifests) currently lack a unified schema contract. Fields drift per team, new keys arrive without version bumps, KPI definitions change retroactively, and CI cannot detect incompatible changes. The roadmap demands per-file governance before we expand the success scoring model. Without an authoritative schema layer and pinned KPI math, downstream analytics, replay tooling, and customer dashboards remain brittle and unverifiable.

## 2. Decision

Adopt a schema governance program that:

1. Stamps every persisted artifact with `$schema_name` + `$schema_version` (semver).
2. Requires field-level `stability` metadata and migration notes for any breaking change.
3. Pins KPI formulas (`plan_adherence`, `tool_coverage`, `veto_count`, `success`) in code + docs, with tests that assert the math.
4. Adds a CI “schema guard” that blocks merges lacking updated schema manifests, rationale, and migration stubs.

### 2.1 Schema metadata rules

- **Per-file manifest:** Each JSON/JSONL header includes `{ "$schema_name": "<artifact>", "$schema_version": "X.Y.Z" }`. Writers must bump versions using semver (major = breaking, minor = additive, patch = metadata).
- **Field registry:** Schema definitions live under `internal_docs/schema/<artifact>.yaml` with entries `path`, `type`, `stability` (`stable`, `beta`, `experimental`), and `since`.
- **Migration notes:** Every field with downgraded stability or incompatible semantics must link to `MIGRATIONS.md` entry and include `migration_note` text in the ADR/PR.
- **Automation:** `scripts/schema_guard.py` compares checked-in schema YAML with generated JSON schema snapshots in `noesis/schemas/generated/`. Drift without a corresponding semver bump fails CI.

### 2.2 KPI definitions (pinned)

Formulas source from `noesis/metrics/kpi.py` and must remain deterministic per schema version. Aggregates are computed per episode:

- `plan_adherence = completed_steps / planned_steps` (clamped 0–1; planned_steps ≥ 1 enforced).
- `tool_coverage = unique_tools_used / tools_allowed` (default denominator = count of tools in orchestration plan; 0 denominator yields 0 coverage).
- `veto_count = Σ veto events emitted by governance agents (severity ≥ warning)`.
- `success = weighted_sum(plan_adherence, tool_coverage, veto_penalty, outcome_score)` where weights live in configuration but default to `{0.35, 0.35, -0.2, 0.5}` and sum to 1. Any change to weights or math requires semver bump + KPI regression tests.

### 2.3 CI schema guard

- **Inputs:** schema YAML, generated JSON Schemas, KPI formula snapshots, migration note stubs.
- **Checks:** (1) ensure `$schema_version` tags exist in sample fixtures, (2) detect field removals or type changes without major version bump, (3) require `docs/kpis.md` + `noesis/metrics/kpi.py` updates when KPI coefficients change, (4) verify ADR metadata includes rationale/consequences/alternatives/acceptance/migration stub.
- **Outputs:** machine-readable report stored in `artifacts/schema_guard.json` for observability dashboards.

## 3. Consequences

- Schema evolution becomes auditable; downstream consumers can gate on `$schema_version`.
- KPI dashboards gain determinism because math changes require explicit review + tests.
- CI prevents accidental breaking changes and enforces documentation hygiene.
- Additional upfront effort (writing migration notes, bumping versions) slows quick experiments but reduces firefighting for analytics and customer reports.

## 4. Alternatives considered

1. **Rely on protobuf/Avro registry.** Rejected: requires runtime conversion and does not solve KPI pinning or JSON-first compatibility promised to customers.
2. **Manual wiki tracking.** Rejected: no enforcement mechanism; history already shows drift within weeks.
3. **Only apply governance to `summary.json`.** Rejected: `events.jsonl` drives most analytics, and ungoverned streams would reintroduce inconsistency.

## 5. Acceptance criteria

- All artifact writers emit `$schema_name` + `$schema_version` and reference generated schema docs.
- Schema YAML files list every persisted field with `stability` metadata; CI fails if missing.
- KPI formulas are unit-tested with golden fixtures; PRs changing math must update tests + docs.
- `scripts/schema_guard.py` runs in CI, producing success/failure status and attaching the report to build artifacts.
- `MIGRATIONS.md` contains entries for every breaking change, each citing ADR-003.
- Documentation (`docs/kpis.md`, `internal_docs/schema/*`) reflects the canonical definitions.

## 6. Migration plan

1. Introduce schema YAML + generator scaffolding; dual-write `$schema_version` tags while keeping legacy consumers tolerant (ignore unknown metadata).
2. Build schema guard CI job (GitHub Action `schema-governance.yml`) that runs generator diff + KPI tests.
3. Backfill historical schema versions for existing artifacts; add `migration_note` entries describing assumptions and inferred defaults.
4. Update artifact writers to require explicit schema version arguments; block merges if omitted.
5. Freeze KPI weights in `noesis/metrics/kpi.py`; add regression suite comparing historical episodes vs stored expectations.
6. Flip CI requirement to blocking once all teams adopt version tags (target Phase 0 exit).

### 6.1 Migration note stub

```
- **Component:** <artifact/field/KPI>
- **Old behavior:** <brief>
- **New behavior:** <brief>
- **Schema version:** <X.Y.Z>
- **Breaking?:** yes/no (explain)
- **Follow-up tasks:** <links>
```

Include this stub (filled) in `MIGRATIONS.md` for each breaking change introduced while implementing ADR-003.

## 7. Open questions / risks

- Where should stability metadata live for non-JSON assets (e.g., parquet exports)? Proposal: embed sidecar YAML referencing the same semver tags.
- Do we enforce schema version monotonicity across branches? Need rule for hotfix branches bumping patch versions.
- KPI weighting governance: does Product Insights own the baseline weights, or do we need an RFC every time they change?
- Performance impact of schema guard on large JSONL fixtures—may require sampling or streaming diff.

## 8. References

- ROADMAP Phase 0 entry “Schema governance & KPIs”.
- `internal_docs/adr/ADR-002-artifact-integrity.md` (manifest + IDs that embed schema tags).
- `MIGRATIONS.md` policy doc.
- `docs/kpis.md`, `noesis/metrics/kpi.py` (implementation targets).
- Pending GitHub Action spec `ci/schema-governance.yml`.
