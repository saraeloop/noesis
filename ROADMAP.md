# Noēsis Roadmap
**Program Increment:** v0.9.5 → v1.0.0  
**Audience:** Core Engineering, Research, and QA

---

## Vision

Noēsis is a **cognitive framework** — not a workflow engine, not a chat orchestrator.  
It formalizes reasoning as a *structured cognitive process* that is **observable, extensible, and testable**.

> “We build like engineers. We reason like researchers.”  
> Noēsis bridges software architecture and cognitive science — aligning rigor from insights like **ReAct**, **Reflexion**, **Voyager**, **Tree of Thoughts**, **Self-Discover**, and **Meta-CoT**.

Every update strengthens three dimensions:
- **Cognitive fidelity:** Observe → Interpret → Plan → Act → Reflect → Learn
- **Architectural purity:** clear domain boundaries, dependency inversion, zero side effects
- **Framework agnosticism:** interoperable with LangGraph, CrewAI, OpenDevin, MCP, etc., but dependent on none.

---

## Completed (Stable)

### Cognitive Core (v0.7.0 — Stable)
- ✅ Formalized cognitive verbs with distinct event schemas and metrics (`domain/state/cognitive.py`, `trace/schema.py`).
- ✅ Added causal lineage wiring (`caused_by`) across cognitive phases (`usecases/episode_runner.py`).
- ✅ Unified cognitive clock with phase durations (`runtime/clock.py`).
- ✅ Installed meta-phase hooks for governance and introspection (`usecases/hooks/meta_phase.py`).

### Faculty System (v0.8.0 — Stable)
- ✅ Deterministic Intuition heuristics with optional LLM shims (`domain/faculties/intuition.py`).
- ✅ Depth/beam-limited `MetaPlanner` with directive mutation and PlannerMode toggles (`domain/planner/meta.py`, `domain/faculties/direction.py`).
- ✅ Insight metrics builder persisting versioned KPIs (`domain/faculties/insight.py`).
- ✅ Pre-act governance with audit/veto lineage wiring (`domain/faculties/governance.py`, `usecases/episode_runner.py`).

### Diagnostics & Observability (v0.8.x — Stable)
- ✅ Faculty schema registry and versioned JSON Schemas (`domain/faculties/versioning.py`, `trace/schema/`).
- ✅ Golden fixtures guarding planner/governance payloads (`tests/golden/`).
- ✅ Hook-order validator and LangGraph adapter fixtures (`tests/runtime/test_hook_order.py`, `tests/integration/test_cognitive_events.py`).
- ✅ Insight finalize tests to protect metric determinism (`tests/insight/test_finalize_metrics.py`).

### Accepted Baseline Metrics
| Capability | Target | Status |
|------------|--------|--------|
| Cognitive loop fidelity | 99 % phase coverage; lineage ≥ 95 %; veto latency < 250 ms | ✅ Stable |
| Direction (ToT) | ≥ 80 % success; avg branch ≤ 5; prune < 150 ms | ✅ Stable |
| Memory | precision@3 ≥ 0.7; recall < 300 ms/query | ✅ Stable |
| Learning feedback | +15 % policy gain; rollback ≤ 5 % deviation | ✅ Stable |
| Governance & Insight | trust std dev < 0.1; drift recall ≥ 80 % | ✅ Stable |

---

## Road to v1.0.0 (In Progress)

### Guiding Objectives
- Deterministic governance/direction lineage with stable identifiers.
- Version-safe schemas with developer-friendly diagnostics.
- Reproducible curricula and replay harness for scientific validation.
- Transparent documentation and schema references for contributors.
- Signed releases with enforced replay gates and migration reporting.

### Phase Sequence

#### Phase 0 — No-Surprises, No-Gaps (Blocking)
**Focus:** Lock the “trust spine” contracts (runtime owner, artifact immutability, schema governance) before landing more PRs.

**Key Deliverables**
- **Runtime RFC:** Document the single-session runtime object (threading, ownership, env-var defaults), the `ns.*` shims that wrap it, and the typed Runner/graph adapter contract used by `run/solve`.
- **Artifact Spec:** Finalize directory layout (`events.jsonl`, `summary.json`, `state.json`, `manifest.json`, optional `learn.jsonl`), ULID episode IDs plus derived UUIDv5 directive/governance IDs, and write-once rules (temp file → atomic rename, manifest with size + sha256 + optional HMAC).
- **Schema Governance Doc:** Per-file `$schema_version`, field-level `stability` flags, semver policy + migration-note checklist, and glossary that pins KPI formulas (plan_adherence, tool_coverage, veto_count, success, etc.).
- **Determinism Drill:** Paper (or notebook) replay of a vetoed episode that exercises the new IDs/manifest, a minimal-mode artifact diff proving byte-identical outputs, and a manual enforcement checklist that bridges to later CI gates.

**Blocking Workstreams (PR-gated)**
1. **ADR-001 — Runtime ownership & NoesisSession** *(Owner: Sara)*  
   Scope: single session object, threading/reentrancy guarantees, `ns.*` shims, Runner/graph adapter contract, env-defaulting without hidden globals.
2. **ADR-002 — Artifact immutability & manifest** *(Owner: Sara)*  
   Scope: episode directory layout, temp→atomic write policy, `manifest.json` schema (sizes + SHA256 + optional HMAC), ULID episode IDs, UUIDv5 directive/governance IDs, and `noesis artifacts verify` behavior.
3. **ADR-003 — Schema governance & KPIs** *(Owner: Sara)*  
   Scope: per-file `$schema_version`, field-level stability flags, schema semver rules, mandatory migration notes, pinned KPI formulas (plan_adherence, tool_coverage, veto_count, success), and CI schema guard requirements.  
   *Each ADR PR must include rationale, consequences, alternatives rejected, acceptance criteria, and a migration-note stub.*
4. **Determinism Drill PR** *(Owner: Sara)*  
   Deliverables: deterministic vetoed fixture, minimal-mode paired runs proving byte-identical artifacts, `diagnostics --replay` diff spec (lineage, duration tolerances, KPIs), and enforcement that minimal mode emits zero Direction/Governance events while meta mode shows tamper-evident manifests.
5. **NoesisSession spike PR** *(Owner: Sara)*  
   Deliverables: thin `NoesisSession` shell + adapters, one vertical slice (run→plan→act→summarize) on the session, concurrency guarantees, and an impact report (breaking changes, shims, touched files, migration estimate). Out of scope: full CLI migration or docs rewrite.

**Exit Criteria**
- Every engineer can whiteboard an episode lifecycle (session → IDs → artifacts → manifest) without disagreement.
- Simulated vetoed action yields deterministic directive/governance IDs and manifest entries the team can follow step-by-step.
- Schema bumps cannot merge without an accompanying migration note template and reviewer checklist.
- Minimal-mode artifact pairs diff to zero when seeded identically; divergences are explained in the drill log.

#### Phase 1 — Governance & Direction Hardening (v0.9.5)
**Focus:** Stabilize directive/governance identifiers, error handling, and legacy compatibility.  
**Key PRs**
- `PR-1a` Stable IDs (dual-write): emit `directive_id` / `governance_id` alongside legacy fields, add `schema_version`, document in `MIGRATIONS.md`, and cover lineage determinism + dual-field presence.
- `PR-1b` `_apply_directive` errors: tighten word-boundary matching, include directive ID and matched rule in failure messages, snapshot diagnostics.
- `PR-1c` Minimal-mode regression: guarantee zero Direction/Governance events and no `summary["insight"]` side-effects under `PlannerMode=minimal`.
**Exit Criteria**
- Direction→Governance→Act events carry stable IDs and deterministic lineage.
- Minimal planner mode remains free of governance artifacts (events and summaries).
- Error surfaces actionable context for operator debugging.

#### Phase 2 — Schema Registry & Diagnostics (v0.9.6)
**Focus:** Centralize schema management with CI enforcement and developer tooling.  
**Key PRs**
- `PR-2a` Schema registry + guard: move versioned JSON Schemas into `docs/schema/`, add registry loader, fail CI on unversioned diffs (expect `pyproject.toml` / `uv.lock` churn).
- `PR-2b` Diagnostics integration: run schema checks inside `noesis diagnostics --check-all` and `scripts/pre_release.py`; document recovery steps for schema drift.
**Exit Criteria**
- Local diagnostics flag schema mismatches before CI.
- PRs without schema version bumps are blocked automatically.
- README/Contributing detail remediation workflow.

#### Phase 3 — Curriculum & Replay (v0.9.7)
**Focus:** Ship reproducible curricula and episode replay harness.  
**Key PRs**
- `PR-3a` Replay harness: add `diagnostics --replay` with golden diffs for lineage, durations, and insight metrics; fixtures live under `tests/fixtures/`.
- `PR-3b` Curriculum runner: define `curriculum.jsonl` format, sampling rules, and example dataset; integration tests with golden directories (call out review time).
**Exit Criteria**
- Replay CLI returns non-zero on drift beyond thresholds.
- Curriculum runner executes published datasets with deterministic artifacts.
- Integration suite stable on Linux/py311/py312.

#### Phase 4 — Documentation & Schema Reference (v0.9.8)
**Focus:** Make cognition and schema contracts transparent.  
**Key PRs**
- `PR-4a` Docs build discipline: require `pnpm --dir docs install && pnpm --dir docs run build` in every PR checklist.
- `PR-4b` Auto schema pages: generate schema reference MDX with cache-bust and extend “Contracts” page with Stable vs Experimental matrix.
**Exit Criteria**
- Docs build runs in CI and locally with identical commands.
- Schema references publish examples alongside version metadata.
- Faculty lifecycle diagrams accessible from `docs/app/reference/index.mdx`.

#### Phase 5 — Release Integrity (v1.0.0)
**Focus:** Production-grade releases with attestations and migrations.  
**Key PRs**
- `PR-5a` Signing workflow: configure artifact attestations, coordinate secrets/permissions task before merge, and gate releases on replay success.
- `PR-5b` Migration report: keep migration diff in `RELEASE.md`, link from docs, and have CI generate migration snippets automatically.
**Exit Criteria**
- Tagged releases fail if replay gate detects drift.
- Distributed artifacts are signed and publish attestations.
- Release notes include autogenerated changelog + migration guidance.

### v1.0.0 Release Gate
- Curriculum runs (smoke + regression + Meta-CoT) auto-compare outputs.
- Reasoning-depth score increases ≥ 10 % between policy versions.
- Docs deploy passes link + diagram checks.
- Schema guard rejects incompatible events in CI.
- Signed release verifies artifact attestations.
- Version matrix published and validated against release artifacts.

---

## Engineering Operating Rules (apply to every PR)
- Follow Clean Architecture boundaries (Entities → Use Cases → Interface Adapters → Infrastructure) with strong typing, pathlib, dependency injection, and explicit namespaces (no spelunking through `core` internals).
- Keep orchestration separate from data models; favor pure functions/dataclasses; IO stays at infrastructure edges; every feature must preserve artifact immutability (append-only events, atomic writes, manifest updates) and uphold minimal-mode guarantees (zero Direction/Governance events, empty insight metrics).
- PR checklist template: ADR linked (or N/A) with acceptance criteria, Clean Architecture boundaries clear, mypy/pyright clean, pytest updated, determinism fixture refreshed, diagnostics plan updated (or N/A), docs + migration notes added, artifacts immutable.
- Required tests: entities/use cases unit tests, integration run that emits expected artifacts, determinism test showing minimal-mode golden byte-identical, governance latency budget captured in diagnostics specs (hard enforcement arrives in Phase 2).

---

## Future (Post v1.0.0)

### Meta-Cognition Layer (v1.1+ Exploration)
- Meta-loop reflection: allow episodes to introspect traces and adjust heuristics mid-run (potential `ReflectOnSelf` phase).
- Cognitive graph reasoning: connect episodes in a graph to visualize influence and learning transfer.
- Policy gradient from insight metrics: treat `plan_adherence`, `veto_rate`, and `success_rate` as reinforcement signals for adaptive policies.
- Introspective policy proposals: route governance veto outcomes into LearningPort.
- Cognitive fingerprinting: cluster reasoning styles via trace embeddings and personalize curricula.

### Ecosystem Enhancements
- Textual episode viewer (TUI) behind `noesis[ui]` with timeline/metrics/governance panes.
- `noesis new-episode --danger-demo` helper for sandbox demos.
- Meta-CoT & Self-Discover benchmarks expanded inside curriculum metrics.
- Canonicalized `policy_score` metric reused across learning and curriculum acceptance tests.
- Runtime × schema × policy version matrix maintained in public docs.
- LangGraph + human approval incident triage demo refactor.
- Strict phase typing and logging hooks in `noesis/trace/events.py`.
- Workflow automation tests for CI bots and issue templates.

---

## Tech Debt & Intake (Ongoing Backlog)
- Document release freeze window ahead of GA to stabilize APIs.
- Convert staged drafts under `internal_docs/issue-drafts/` into GitHub issues with owners.
- Expand replay datasets under `benchmarks/` once the curriculum harness lands.
