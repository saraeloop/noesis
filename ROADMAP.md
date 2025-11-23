# Noēsis Roadmap

**Program Increment:** v0.9.5 → v1.0.0  
**Audience:** Core Engineering, Research, and QA

---

## Vision

Noēsis is a **cognitive framework** — not a workflow engine, not a chat orchestrator.  
It formalizes reasoning as a _structured cognitive process_ that is **observable, extensible, and testable**.

> “We build like engineers. We reason like researchers.”  

Noēsis bridges software architecture and cognitive science — aligning rigor from insights like **ReAct**, **Reflexion**, **Voyager**, **Tree of Thoughts**, **Self-Discover**, and **Meta-CoT**.

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
| Cognitive loop fidelity | 99 % phase coverage; lineage ≥ 95 %; veto latency < 250 ms | ✅ Stable |
| Direction (ToT)         | ≥ 80 % success; avg branch ≤ 5; prune < 150 ms             | ✅ Stable |
| Memory                  | precision@3 ≥ 0.7; recall < 300 ms/query                   | ✅ Stable |
| Learning feedback       | +15 % policy gain; rollback ≤ 5 % deviation                | ✅ Stable |
| Governance & Insight    | trust std dev < 0.1; drift recall ≥ 80 %                   | ✅ Stable |

---

## Road to v1.0.0 (In Progress)

### Guiding Objectives

- Deterministic cognition: stable governance/direction lineage and byte-identical minimal runs.
- Version-safe schemas with developer-friendly diagnostics.
- Transparent documentation and schema references for contributors.
- Signed releases with enforced replay gates and migration reporting.
- Lay groundwork for **Prompt Provenance** (ADR-005) as an opt-in, experimental runtime artifact — without blocking v1.0.0.

### Phase Sequence

---

### Phase 0 — Trust Spine  
(**DONE; determinism substrate shipped, drill UX pending**)

**Focus:** Lock the “trust spine” contracts (runtime owner, artifact immutability, schema governance).

**Key Deliverables**

- **Runtime RFC:** Document the single-session runtime object (threading, ownership, env-var defaults), the `ns.*` shims that wrap it, and the typed Runner/graph adapter contract used by `run/solve`. (Implemented; ADR-001 pending acceptance.)
- **Artifact Spec:** Finalize directory layout (`events.jsonl`, `summary.json`, `state.json`, `manifest.json`, optional `learn.jsonl`), ULID episode IDs plus derived UUIDv5 directive/governance IDs, and write-once rules (temp file → atomic rename, manifest with size + sha256 + optional HMAC). (ADR-002 completed.)
- **Schema Governance Doc:** Per-file `$schema_version`, field-level `stability` flags, semver policy + migration-note checklist, and glossary that pins KPI formulas (plan_adherence, tool_coverage, veto_count, success, etc.). (ADR-003 completed.)
- **Determinism substrate (ADR-004):** Canonical serialization + atomic writes, deterministic clock/RNG, deterministic ULID/UUID lineage, event helpers wired with `now_fn`/`id_factory`, and structural replay tests guarding summary/state/manifest/events. (Implemented; drill UX still open.)

**Blocking Workstreams (PR-gated)**

1. ~~**ADR-001 — Runtime ownership & NoesisSession** _(Owner: Sara)_~~ **(Implemented; ADR status pending acceptance)**  
   Scope: single session object, threading/reentrancy guarantees, `ns.*` shims, Runner/graph adapter contract, env-defaulting without hidden globals; formal GA and acceptance still required.

2. ~~**ADR-002 — Artifact immutability & manifest** _(Owner: Sara)_~~ **(Completed)**  
   Scope: episode directory layout, temp→atomic write policy, `manifest.json` schema (sizes + SHA256 + optional HMAC), ULID episode IDs, UUIDv5 directive/governance IDs, and `noesis artifacts verify` behavior.

3. ~~**ADR-003 — Schema governance & KPIs** _(Owner: Sara)_~~ **(Completed)**  
   Scope: per-file `$schema_version`, field-level stability flags, schema semver rules, mandatory migration notes, pinned KPI formulas (plan_adherence, tool_coverage, veto_count, success), and CI schema guard requirements.

4. **Determinism Drill (tooling) PR** _(Owner: Sara)_  
   Deliverables: replay CLI (`diagnostics --replay` or equivalent) that re-runs an episode under `DeterminismConfig`, diffs artifacts/lineage with tolerances, emits clear DRIFT/NO DRIFT, and a named vetoed golden used by both CLI and CI.

**Exit Criteria**

- Every engineer can whiteboard an episode lifecycle (session → IDs → artifacts → manifest) without disagreement.
- Simulated vetoed action yields deterministic directive/governance IDs and manifest entries the team can follow step-by-step.
- Schema bumps cannot merge without an accompanying migration note template and reviewer checklist. (Met by ADR-003 guard.)
- Minimal-mode artifact pairs diff to zero when seeded identically; divergences are explained in the drill log. (Pending determinism drill tooling.)

---

### Phase 1 — Determinism Drill (Blocking for v1.0.0)

**Focus:** Ship the replay/drift UX on top of the deterministic runtime.

**Key Deliverables**

- `diagnostics --replay` (or equivalent) to re-run episodes under `DeterminismConfig` and report DRIFT/NO DRIFT across summary/state/manifest/events with tolerances for metrics.
- Paired meta/minimal runs with goldens; minimal-mode artifacts are byte-identical across seeds; meta-mode shows tamper-evident manifests.
- Simulated veto scenario golden exercising ULID→UUIDv5 lineage and manifest verification.
- CI gate that fails on replay drift using the canonical golden.

**Exit Criteria**

- Minimal-mode artifacts are bit-for-bit identical across runs.
- Replay tool reports zero drift for goldens.
- Governance lineage is deterministic and validated by goldens.

---

### Phase 2 — NoesisSession GA (ADR-001 → Accepted)

**Focus:** Make the session the public, deterministic entrypoint.

**Key Deliverables**

- Promote ADR-001 from Proposed to Accepted with reentrancy/threading guarantees.
- Document `NoesisSession` / `ns.run/solve` surface as GA; add migration notes.
- Concurrency and ownership tests proving determinism.
- README/docs updated to show session-first usage.

**Exit Criteria**

- Senior engineers can adopt Noēsis without guessing about runtime scope or threading.
- Public API surface and shims are documented; ADR-001 marked Accepted.

---

### Phase 2.5 — Prompt Provenance v0.1  
(ADR-005 — Experimental, **Non-Blocking**)

**Focus:** Record a minimal prompt trace as a runtime artifact without blocking v1.0.0.

**Scope (v0.1 only)**

- Add optional `prompts.jsonl` artifact gated by `prompt_provenance_enabled`.
- Support at least two modes:
  - `full`  
  - `hash_only` (no raw prompt text, only metadata + fingerprint).
- Implement a small `PromptRecorder` in the runtime/trace layer that:
  - lazily opens `prompts.jsonl` under `runs/<label>/<episode_id>/`,
  - normalizes `rendered` and computes a deterministic `fingerprint`,
  - injects `episode_id`, `phase`, `agent_id`, `timestamp`, `model`, `mode`,
  - respects `DeterminismConfig` for timestamps when present,
  - is a no-op when disabled.

- Wire v0.1 only into a small set of Noēsis-owned LLM call sites:
  - Planner / Direction (PLAN),
  - Act (ACT),
  - optionally Governance (GOVERNANCE) where trivial.

- Keep the v0.1 schema narrow:
  - `episode_id`, `phase`, `agent_id`, `rendered`, `fingerprint`, `timestamp`, `model`, `mode`.

**Non-goals (deferred to v1.1+)**

- Full prompt schema in the schema registry (`internal_docs/schema/prompt.yaml`).
- `variables`, `template`, `template_id`, and rich `kind`/`tags` usage.
- `mode="redacted"` and pluggable redaction policies.
- Adapter instrumentation (LangGraph/CrewAI/MCP).
- Prompt-centric UI or analytics.

**Exit Criteria (for v0.1)**

- When `prompt_provenance_enabled=true`, `prompts.jsonl` is created for at least one example scenario. ✅
- Lines contain the minimal field set and join correctly on `episode_id`. ✅
- A small deterministic test case asserts identical `prompts.jsonl` between two runs under the same `DeterminismConfig` (or the feature is explicitly disabled in deterministic mode for v1.0.0).

> **Note:** Phase 2.5 is explicitly **non-blocking** for the v1.0.0 release gate. It can be skipped if capacity is tight; ADR-005 remains Proposed/Experimental and is fully realized in v1.1+.

---

### Phase 3 — Real LLM Example (LangGraph/CrewAI-style)

**Focus:** Prove real-world integration with a live LLM-backed flow.

**Key Deliverables**

- One LangGraph or CrewAI-esque example hitting a real LLM.
- Emits full artifacts + manifest; replay passes with the determinism drill.
- Docs showing how to wrap external tools/graphs with Noēsis.

**Exit Criteria**

- Example reproducible by users with artifacts they can inspect and replay.
- Demonstrates cognitive loop value (plan/govern/reflect) on a real model/tool call.

---

### v1.0.0 Release Gate

- Determinism drill goldens pass locally and in CI (including replay gate).
- Session API is GA and documented (ADR-001 Accepted).
- LLM example artifacts replay without drift.
- Prompt Provenance (ADR-005) may exist in v0.1 form but is **not required** for the v1.0.0 release; if present, it must be clearly documented as experimental and behind a feature flag.

---

## Engineering Operating Rules (apply to every PR)

- Follow Clean Architecture boundaries (Entities → Use Cases → Interface Adapters → Infrastructure) with strong typing, `pathlib`, dependency injection, and explicit namespaces (no spelunking through `core` internals).
- Keep orchestration separate from data models; favor pure functions/dataclasses; IO stays at infrastructure edges.
- Every feature must:
  - preserve artifact immutability (append-only events, atomic writes, manifest updates),
  - uphold minimal-mode guarantees (zero Direction/Governance events, empty insight metrics).

- PR checklist template:
  - ADR linked (or N/A) with acceptance criteria,
  - Clean Architecture boundaries clear,
  - mypy/pyright clean,
  - pytest updated,
  - determinism fixture refreshed (or N/A),
  - diagnostics plan updated (or N/A),
  - docs + migration notes added,
  - artifacts remain immutable.

- Required tests:
  - entities/use cases unit tests,
  - integration run that emits expected artifacts,
  - determinism test showing minimal-mode golden byte-identical,
  - governance latency budget captured in diagnostics specs (hard enforcement arrives in Phase 2).

---

## Future (Post v1.0.0)

### Prompt Provenance & Cognitive Provenance (ADR-005) — v1.1+

- Promote `prompts.jsonl` to a full, schema-governed artifact:
  - `internal_docs/schema/prompt.yaml` + generated JSON Schema,
  - field-level `stability` and semver rules,
  - schema_guard integration and fixtures.
- Expand coverage to all cognitive phases:
  - observe / interpret / plan / governance / act / reflect / learn.
- Add richer fields:
  - `template`, `template_id`, `variables`, `kind`, `tags`.
- Implement robust privacy modes:
  - `hash_only` and `redacted` as first-class deployment knobs,
  - optional redaction policies for PII/secret suppression.
- Wire prompt fingerprints into `events.jsonl` for join-friendly provenance graphs.
- Provide examples + DeepWiki docs showing:
  - prompt-level drift analysis,
  - ablations over prompt variants,
  - cognitive provenance diagrams grounded in Noēsis artifacts.

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
