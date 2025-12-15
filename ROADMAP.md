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

### Prompt Provenance (ADR-005) — Experimental, Opt-in (Completed)

- ✅ Schema-governed prompt records (`$schema_name: prompt`, `$schema_version: 1.1.0`) with fixtures and schema guard (`internal_docs/schema/prompt.v1.yaml`, `docs/schema/prompt/1.1.0.json`, `tests/runtime/test_prompt_schema.py`).
- ✅ PromptRecorder with `full` / `hash_only` / `redacted` modes, deterministic hashing, manifest integration, and leakage guards (`noesis/runtime/prompt_recorder.py`, `tests/runtime/test_prompt_recorder.py`).
- ✅ Recorded prompts across interpret, plan, governance, and reflect phases with tag threading and event linkage where available (`noesis/usecases/episode_runner.py`).
- ✅ Docs updated to mark prompts.jsonl experimental with mode semantics and schema reference (`docs/runs/README.md`).

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
- Prompt provenance shipped as an experimental, opt-in artifact (ADR-005 v1.1); adapters/UI remain out of scope.

### Current Status (at a glance)

- ✅ Prompt provenance v1.1 (experimental, opt-in) shipped with schema/modes/tests.
- ✅ Minimal-mode deterministic goldens + replay comparator (`diagnostics replay`); veto scenario determinism covered in tests.
- ✅ ADR-001 Accepted; session API documented.
- ⚠️ Determinism drill: CI replay gate still needed (golden/regression wired into CI).
- ⚠️ Session GA proof: threading/ownership/reentrancy tests added; keep them enforced in CI.
- ⚠️ Real LLM example missing: no checked-in live-model run that passes replay.

### v1.0.0 — Definition of Done (Remaining Work)

Noēsis v1.0.0 is considered **complete** when all of the following are true:

1. **Determinism Drill is a CI Gate**
   - A vetoed episode golden is checked in (non-minimal mode).
   - `noesis diagnostics replay` is wired into CI to replay goldens and fail on drift across `summary.json`, `state.json`, `events.jsonl`, and `manifest.json`.

2. **NoesisSession GA is Verified, Not Just Documented**
   - Threading / ownership / reentrancy tests for `NoesisSession` are present and run in CI (parallel sessions, reuse semantics, no global state leaks).
   - ADR-001 remains Accepted and matches the behaviour enforced by these tests.

3. **Real LLM Example Has a Passing Golden**
   - At least one checked-in example uses a real LLM-backed agent/graph, emits the full artifact suite, and its recorded run passes the determinism replay gate in CI.

Once these three conditions are met, the Noēsis runtime and artifact model are considered **v1.0.0-complete**. Further work (curriculum runner, dashboards, expanded prompt provenance, etc.) is tracked under v1.1+ and is not blocking GA.

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
   Deliverables: replay CLI (`diagnostics replay`) that re-runs an episode under `DeterminismConfig`, diffs artifacts/lineage with tolerances, emits clear DRIFT/NO DRIFT, and a named vetoed golden used by both CLI and CI. **Status:** CLI + comparer + minimal-mode goldens shipped; vetoed golden + CI gate outstanding.

**Exit Criteria**

- Every engineer can whiteboard an episode lifecycle (session → IDs → artifacts → manifest) without disagreement.
- Simulated vetoed action yields deterministic directive/governance IDs and manifest entries the team can follow step-by-step.
- Schema bumps cannot merge without an accompanying migration note template and reviewer checklist. (Met by ADR-003 guard.)
- Minimal-mode artifact pairs diff to zero when seeded identically; divergences are explained in the drill log. (Pending determinism drill tooling.)

---

### Phase 1 — Determinism Drill (Partially Complete; still blocking v1.0.0)

**Focus:** Ship the replay/drift UX on top of the deterministic runtime.

**Delivered**

- `diagnostics replay` CLI with structural/byte diffing (`noesis/cli/commands/diagnostics.py`, `noesis/diagnostics/replay.py`).
- Minimal-mode deterministic goldens + unit tests (`tests/golden/deterministic_run/run_{a,b}`, `tests/diagnostics/test_replay.py`).

**Remaining (Blocking)**

- Add a CI-enforced replay gate (drift check) and persist a veto scenario regression (golden or generated fixture).

**Exit Criteria**

- Minimal-mode artifacts are bit-for-bit identical across runs (covered by current goldens).
- Replay tool reports zero drift for goldens in CI.
- Governance lineage determinism validated by a vetoed golden.

---

### Phase 1.7 — Governance Modes (ADR-007 — Proposed)

**Focus:** Make governance an explicit 3-mode faculty (**off / audit / enforce**) with canonical veto semantics and schema-governed signaling.

**Faculty order (canonical):** Intuition → Direction → Governance → Insight. Governance is **pre-act** and runs **after** Direction has produced a plan.

**Delivered**

- None; ADR-007 drafted with canonical status and event semantics.

**Remaining (Blocking)**

- Add `governance.mode` (`off` default) and `governance.failure_policy` defaults (**audit: fail_open**, **enforce: fail_closed**, with override).
- Enforce canonical episode outcome **`vetoed`** (episode-level). Keep **`blocked`** as an **event-level** reason only (direction/governance events). **`blocked` MUST NOT appear as an episode outcome.**
- Veto scope: In **enforce**, a **pre-act veto terminates the episode** with outcome `vetoed` (not “skip one step and continue”), and **no Act event is emitted**.
- Governance event schema (ADR-003 governed): minimal required fields  
  (`mode`, `failure_policy`, `enforced`, `decision`, `policy_id`, `policy_version`, `policy_kind`, `rule_id`, `score`, `message`, `caused_by`; optional `details`, `suggested_fixes`, `error`).
  - Consistency rule: `enforced == (mode == "enforce")`.
  - Failure semantics: `fail_closed` ⇒ treat policy failure/timeout as **VETO** and emit `error` metadata in the governance payload.
- Policy contract stays pure: input (**goal, plan**, optional minimal **context** if defined), output `GovernanceResult` (decision/rule/message/score/fixes), **no side effects**.
- Tests:
  - Unit coverage for **off/audit/enforce**.
  - Integration: **“enforce veto terminates before Act”** with terminate/summary status `vetoed`.
  - Governance + `direction_blocked` events recorded with lineage (`caused_by`).
  - Determinism golden includes at least one **enforce-veto** episode and is wired into the replay gate.
- Docs:
  - “Governance modes”
  - “What veto means” (outcome vs event reason)
  - Failure policy semantics (fail_open vs fail_closed)
  - Link the enforce-veto golden episode to the replay gate docs.

**Exit Criteria**

- Governance mode/config defaults are explicit and test-backed.
- Episode-level outcome `vetoed` is canonical across `summary.json`, `state.json`, and terminate semantics (where applicable).
- Governance events are schema-governed and lineage-linked; **audit never blocks**, **enforce fail-fast blocks Act** and terminates the episode.
- Determinism/replay gate includes at least one enforce-veto golden.


### Phase 2 — NoesisSession GA (ADR-001 → Accepted; finalize GA proof)

**Focus:** Make the session the public, deterministic entrypoint.

**Delivered**

- ADR-001 marked Accepted; session API documented (`NoesisSession`, `SessionBuilder`, `ns.run/solve`).

**Remaining**

- Keep threading/ownership/reentrancy tests enforced in CI.
- Ensure docs/readme call the session API GA with migration notes.

**Exit Criteria**

- Senior engineers can adopt Noēsis without guessing about runtime scope or threading.
- Public API surface and shims are documented; ADR-001 stays Accepted with GA tests in CI.

---

### Phase 2.5 — Prompt Provenance v1.1 (Completed)  
(ADR-005 — Experimental, **Non-Blocking**)

**Focus:** Ship schema-governed prompt provenance with multi-phase coverage and privacy modes.

**Delivered**

- Optional `prompts.jsonl` artifact gated by `prompt_provenance_enabled` with `full`, `hash_only`, and `redacted` modes.
- Schema-governed prompt records (`$schema_name: "prompt"`, `$schema_version: "1.1.0"`) covering identity, context, content, provenance, and tags.
- PromptRecorder with deterministic fingerprinting, redaction, and tag support; manifest integration and determinism guard.
- Recorded prompts across core phases: interpret (intuition), plan (direction.planner), governance (governance.pre_act), reflect (reflect).
- Fixtures + schema guard + runtime tests to prevent leakage in non-full modes.

**Notes**

- Still experimental/opt-in; adapters (LangGraph/CrewAI/MCP) remain out of scope.
- Future UI/analytics remain out of scope; this phase completes ADR-005’s runtime/governance surface.

---

### Phase 3 — Real LLM Example (LangGraph/CrewAI-style)

**Focus:** Prove real-world integration with a live LLM-backed flow.

**Remaining**

- Add one LangGraph/CrewAI-esque example hitting a real model.
- Ensure it emits full artifacts + manifest and passes replay/determinism checks.
- Document how to wrap external tools/graphs with Noēsis using this example.

**Exit Criteria**

- Example reproducible by users with artifacts they can inspect and replay.
- Demonstrates cognitive loop value (plan/govern/reflect) on a real model/tool call.

---

### v1.0.0 Release Gate

- Determinism drill goldens pass locally and in CI (including replay gate).
- Session API is GA and documented (ADR-001 Accepted).
- LLM example artifacts replay without drift.
- Prompt Provenance (ADR-005) exists as an experimental, opt-in artifact (`prompt@1.1.0`) but is **not required** for the v1.0.0 release; it must remain clearly documented as experimental and behind a feature flag (not part of the replay gate).

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

### Prompt Provenance & Cognitive Provenance (ADR-005) — v1.2+

- Expand coverage to all cognitive phases (add observe/act/learn paths).
- Wire prompt fingerprints into `events.jsonl` for direct joinability.
- Provide higher-level examples/notebooks for drift and incident analysis.
- Optional: per-field redaction/PII policies and adapter opt-ins (LangGraph/CrewAI/MCP).

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
