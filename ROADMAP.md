# Noēsis Roadmap

**Program Increment:** v0.9.5 → v1.0.0  
**Audience:** Core Engineering, Research, and QA

---

## Vision

Noēsis is a **cognitive framework** — not a workflow engine, not a chat orchestrator.  
It formalizes reasoning as a _structured cognitive process_ that is **observable, extensible, and testable**.

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

### Artifact Immutability & Manifests (ADR-002 — Stable)

- ✅ ULID-based episode IDs plus deterministic Directive/Governance UUIDv5 derivations (`runtime/artifacts/ids.py`, `usecases/episode_runner.py`).
- ✅ Atomic JSON writers with dir fsyncs for `state.json`/`summary.json`, manifest builder + HMAC signing (`runtime/artifacts/*`, `infrastructure/state_repository.py`).
- ✅ CLI + diagnostics enforcement for `manifest.json` (`noesis artifacts verify`, `diagnostics`), plus `noesis.artifacts.verify_manifest` public API surface and `noesis.io` manifest rehash guards.
- ✅ Tests: tamper/missing/extra/mutex coverage, ULID ordering stress, CLI exit codes, and HMAC canonicalization fixtures (`tests/runtime/test_artifacts.py`, `tests/runtime/test_ids.py`, `tests/cli/test_artifacts_cli.py`).

### Accepted Baseline Metrics

| Capability              | Target                                                     | Status    |
| ----------------------- | ---------------------------------------------------------- | --------- |
| Cognitive loop fidelity | 99 % phase coverage; lineage ≥ 95 %; veto latency < 250 ms | ✅ Stable |
| Direction (ToT)         | ≥ 80 % success; avg branch ≤ 5; prune < 150 ms             | ✅ Stable |
| Memory                  | precision@3 ≥ 0.7; recall < 300 ms/query                   | ✅ Stable |
| Learning feedback       | +15 % policy gain; rollback ≤ 5 % deviation                | ✅ Stable |
| Governance & Insight    | trust std dev < 0.1; drift recall ≥ 80 %                   | ✅ Stable |

---

## Road to v1.0.0 (In Progress)

### Guiding Objectives

- Deterministic cognition: stable governance/direction lineage and byte-identical minimal runs.
- Version-safe schemas with developer-friendly diagnostics.
- Transparent documentation and schema references for contributors.
- Signed releases with enforced replay gates and migration reporting.

### Phase Sequence

#### Phase 0 — Trust Spine (DONE except determinism drill)

**Focus:** Lock the “trust spine” contracts (runtime owner, artifact immutability, schema governance).

**Key Deliverables**

- **Runtime RFC:** Document the single-session runtime object (threading, ownership, env-var defaults), the `ns.*` shims that wrap it, and the typed Runner/graph adapter contract used by `run/solve`. (Implemented; ADR-001 pending acceptance.)
- **Artifact Spec:** Finalize directory layout (`events.jsonl`, `summary.json`, `state.json`, `manifest.json`, optional `learn.jsonl`), ULID episode IDs plus derived UUIDv5 directive/governance IDs, and write-once rules (temp file → atomic rename, manifest with size + sha256 + optional HMAC). (ADR-002 completed.)
- **Schema Governance Doc:** Per-file `$schema_version`, field-level `stability` flags, semver policy + migration-note checklist, and glossary that pins KPI formulas (plan_adherence, tool_coverage, veto_count, success, etc.). (ADR-003 completed.)
- **Determinism Drill:** Paper (or notebook) replay of a vetoed episode that exercises the new IDs/manifest, a minimal-mode artifact diff proving byte-identical outputs, and a manual enforcement checklist that bridges to later CI gates. (Still open.)

**Blocking Workstreams (PR-gated)**

1. ~~**ADR-001 — Runtime ownership & NoesisSession** _(Owner: Sara)_~~ **(Implemented; ADR status pending acceptance)**  
   Scope: single session object, threading/reentrancy guarantees, `ns.*` shims, Runner/graph adapter contract, env-defaulting without hidden globals; formal GA and acceptance still required.
2. ~~**ADR-002 — Artifact immutability & manifest** _(Owner: Sara)_~~ **(Completed)**  
   Scope: episode directory layout, temp→atomic write policy, `manifest.json` schema (sizes + SHA256 + optional HMAC), ULID episode IDs, UUIDv5 directive/governance IDs, and `noesis artifacts verify` behavior.
3. ~~**ADR-003 — Schema governance & KPIs** _(Owner: Sara)_~~ **(Completed)**  
   Scope: per-file `$schema_version`, field-level stability flags, schema semver rules, mandatory migration notes, pinned KPI formulas (plan_adherence, tool_coverage, veto_count, success), and CI schema guard requirements.
4. **Determinism Drill PR** _(Owner: Sara)_  
   Deliverables: deterministic vetoed fixture, minimal-mode paired runs proving byte-identical artifacts, `diagnostics --replay` diff spec (lineage, duration tolerances, KPIs), and enforcement that minimal mode emits zero Direction/Governance events while meta mode shows tamper-evident manifests.

**Exit Criteria**

- Every engineer can whiteboard an episode lifecycle (session → IDs → artifacts → manifest) without disagreement.
- Simulated vetoed action yields deterministic directive/governance IDs and manifest entries the team can follow step-by-step.
- Schema bumps cannot merge without an accompanying migration note template and reviewer checklist. (Met by ADR-003 guard.)
- Minimal-mode artifact pairs diff to zero when seeded identically; divergences are explained in the drill log. (Pending determinism drill.)

#### Phase 1 — Determinism Drill (Blocking for v1.0.0)

**Focus:** Prove deterministic cognition and governance lineage.

**Key Deliverables**

- `diagnostics --replay` (or equivalent) that diffs lineage, durations (with tolerance), and KPIs.
- Paired meta/minimal runs with goldens; minimal-mode artifacts are byte-identical across seeds.
- Simulated veto scenario exercising ULID→UUIDv5 lineage and manifest verification.
- CI gate that fails on replay drift.

**Exit Criteria**

- Minimal-mode artifacts are bit-for-bit identical across runs.
- Replay tool reports zero drift for goldens.
- Governance lineage is deterministic and validated by goldens.

#### Phase 2 — NoesisSession GA (ADR-001 → Accepted)

**Focus:** Make the session the public, deterministic entrypoint.

**Key Deliverables**

- Promote ADR-001 from Proposed to Accepted with reentrancy/threading guarantees.
- Document `NoesisSession` / `ns.run/solve` surface as GA; add migration notes.
- Concurrency and ownership tests proving determinism.
- README/docs updated to show session-first usage.

**Exit Criteria**

- Senior engineers can adopt Noēsis without guessing about runtime scope or threading.
- Public API surface and shims are documented; ADR-001 marked Accepted.

#### Phase 3 — Real LLM Example (LangGraph/CrewAI-style)

**Focus:** Prove real-world integration with a live LLM-backed flow.

**Key Deliverables**

- One LangGraph or CrewAI-esque example hitting a real LLM.
- Emits full artifacts + manifest; replay passes with the determinism drill.
- Docs showing how to wrap external tools/graphs with Noēsis.

**Exit Criteria**

- Example reproducible by users with artifacts they can inspect and replay.
- Demonstrates cognitive loop value (plan/govern/reflect) on a real model/tool call.

### v1.0.0 Release Gate

- Determinism drill goldens pass locally and in CI (including replay gate).
- Session API is GA and documented.
- LLM example artifacts replay without drift.

---

## Engineering Operating Rules (apply to every PR)

- Follow Clean Architecture boundaries (Entities → Use Cases → Interface Adapters → Infrastructure) with strong typing, pathlib, dependency injection, and explicit namespaces (no spelunking through `core` internals).
- Keep orchestration separate from data models; favor pure functions/dataclasses; IO stays at infrastructure edges; every feature must preserve artifact immutability (append-only events, atomic writes, manifest updates) and uphold minimal-mode guarantees (zero Direction/Governance events, empty insight metrics).
- PR checklist template: ADR linked (or N/A) with acceptance criteria, Clean Architecture boundaries clear, mypy/pyright clean, pytest updated, determinism fixture refreshed, diagnostics plan updated (or N/A), docs + migration notes added, artifacts immutable.
- Required tests: entities/use cases unit tests, integration run that emits expected artifacts, determinism test showing minimal-mode golden byte-identical, governance latency budget captured in diagnostics specs (hard enforcement arrives in Phase 2).

---

## Future (Post v1.0.0)

### Schema Registry & Diagnostics Polish (v1.1+)

- Harden schema registry UX and diagnostics integrations beyond current guard.
- Expand local tooling and CI dashboards for schema/KPI drift.

### Curriculum & Replay Harness Scale (v1.1+)

- Curriculum runner and larger replay datasets.
- Replay CLI thresholds for scale scenarios.

### Documentation & Schema References (v1.1+)

- Auto-generated schema pages and contracts matrix.
- Docs build discipline and reference updates.

### Release Integrity & Signing (v1.1+)

- Signing/attestations gate releases once replay gates are stable.
- Automated migration snippets in release notes.

### Meta-Cognition & Ecosystem Enhancements (v1.1+ Exploration)

- Meta-loop reflection and cognitive graph reasoning.
- TUI episode viewer, `noesis new-episode --danger-demo`, benchmarks expansion.
- Policy score canonicalization, runtime × schema × policy version matrix.

---

## Tech Debt & Intake (Ongoing Backlog)

- Document release freeze window ahead of GA to stabilize APIs.
- Convert staged drafts under `internal_docs/issue-drafts/` into GitHub issues with owners.
- Expand replay datasets under `benchmarks/` once the curriculum harness lands.
