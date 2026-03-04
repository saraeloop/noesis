# Noēsis Roadmap

**Audience:** Users, contributors, and adopters

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

## Non-goals (v1.x)

Noēsis is a cognitive framework. To protect its identity and prevent scope drift:

- **Not a workflow engine / orchestrator** — use LangGraph, Prefect, etc. for that; Noēsis wraps them.
- **Not a hosted agent platform** — team tooling may come later, but the core stays local-first.
- **Not a prompt library or model router** — provider adapters are thin; prompt engineering is your domain.
- **Not a proprietary lock-in layer** — artifacts are open, schemas are versioned, adapters are optional.

---

## Stability Contract

| Category | Status | Notes |
|----------|--------|-------|
| Artifacts (`events.jsonl`, `state.json`, `summary.json`, `manifest.json`) | **Stable** | Schema-governed, versioned, immutable |
| Session API (`NoesisSession`, `ns.run/solve`) | **Stable** | ADR-001 Accepted |
| Determinism + Replay Gate | **Stable** | CI-enforced, goldens checked in |
| Governance modes (off/audit/enforce) | **Stable** | ADR-007 implemented |
| Prompt Provenance (`prompts.jsonl`) | **Experimental** | Opt-in, schema v1.1, may evolve |
| Provider adapters | **Experimental** | Stable interfaces targeted for v1.2 |
| Dashboards / hosted UI | **Out of scope** | Contract may be defined in v1.3+ |

---

## ADR Queue (Current)

| ADR | Title | Status | Sequence |
|-----|-------|--------|----------|
| ADR-014 | Artifact Contract v1.0 and Sealing Semantics | **Accepted (v1.0 contract)** | Runtime gates enforced (sealing, causality, finalization contract) |
| ADR-015 | Process->Run Interrupt/Checkpoint/Resume Contract | **Proposed (Draft)** | Next: define + implement after ADR-014 acceptance |
| ADR-016 | Protocol-First Tool Contract (subprocess/HTTP/MCP) | **Proposed (Draft)** | After ADR-015 contract boundary is fixed |

Sequencing rule:

- ADR-014 is now the accepted artifact/sealing contract baseline.
- Implement ADR-015 next (durable execution contract), then ADR-016 (protocol-first tool contract).

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
- ✅ Docs updated to mark prompts.jsonl experimental with mode semantics and schema reference (`docs/explanation/artifacts.mdx`).

### Accepted Baseline Metrics

| Capability              | Target                                                     | Status    |
| ----------------------- | ---------------------------------------------------------- | --------- |
| Cognitive loop fidelity | 99 % phase coverage; lineage ≥ 95 %; veto latency < 250 ms | ✅ Stable |
| Direction (ToT)         | ≥ 80 % success; avg branch ≤ 5; prune < 150 ms             | ✅ Stable |
| Memory                  | precision@3 ≥ 0.7; recall < 300 ms/query                   | ✅ Stable |
| Learning feedback       | +15 % policy gain; rollback ≤ 5 % deviation                | ✅ Stable |
| Governance & Insight    | trust std dev < 0.1; drift recall ≥ 80 %                   | ✅ Stable |

---

## v1.0.0 — Shipped (Architectural GA)

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
- ✅ Determinism drill: CI replay gate wired (`determinism-replay.yml` runs `replay_gate.py` on PR/push).
- ✅ Session GA proof: threading/ownership/reentrancy tests added; keep them enforced in CI.
- ✅ Real LLM example: checked-in live-model run replays offline (NO_DRIFT). LLM golden uses sanitized inputs and stores only minimal replay data required for determinism (no secrets, hash-only mode available).

### v1.0.0 — Definition of Done (All Met ✅)

Noēsis v1.0.0 is considered **complete** when all of the following are true:

1. **Determinism Drill is a CI Gate** ✅
   - A vetoed episode golden is checked in (non-minimal mode).
   - `noesis diagnostics replay` is wired into CI to replay goldens and fail on drift across `summary.json`, `state.json`, `events.jsonl`, and `manifest.json`.

2. **NoesisSession GA is Verified, Not Just Documented** ✅
   - Threading / ownership / reentrancy tests for `NoesisSession` are present and run in CI (parallel sessions, reuse semantics, no global state leaks).
   - ADR-001 remains Accepted and matches the behaviour enforced by these tests.

3. **Real LLM Example Has a Passing Golden** ✅
   - At least one checked-in example uses a real LLM-backed agent/graph, emits the full artifact suite, and its recorded run passes the determinism replay gate in CI.

Once these three conditions are met, the Noēsis runtime and artifact model are considered **v1.0.0-complete**. Further work (curriculum runner, dashboards, expanded prompt provenance, etc.) is tracked under v1.1+ and is not blocking GA.

### Phase Sequence

---

### Phase 0 — Trust Spine (DONE)

**Focus:** Lock the “trust spine” contracts (runtime owner, artifact immutability, schema governance).

**Key Deliverables**

- **Runtime RFC:** Document the single-session runtime object (threading, ownership, env-var defaults), the `ns.*` shims that wrap it, and the typed Runner/graph adapter contract used by `run/solve`. (Implemented; ADR-001 Accepted.)
- **Artifact Spec:** Finalize directory layout (`events.jsonl`, `summary.json`, `state.json`, `manifest.json`, optional `learn.jsonl`), ULID episode IDs plus derived UUIDv5 directive/governance IDs, and write-once rules (temp file → atomic rename, manifest with size + sha256 + optional HMAC). (ADR-002 completed.)
- **Schema Governance Doc:** Per-file `$schema_version`, field-level `stability` flags, semver policy + migration-note checklist, and glossary that pins KPI formulas (plan_adherence, tool_coverage, veto_count, success, etc.). (ADR-003 completed.)
- **Determinism substrate (ADR-004):** Canonical serialization + atomic writes, deterministic clock/RNG, deterministic ULID/UUID lineage, event helpers wired with `now_fn`/`id_factory`, and structural replay tests guarding summary/state/manifest/events. (Implemented; drill UX shipped.)

**Blocking Workstreams (PR-gated)**

1. ~~**ADR-001 — Runtime ownership & NoesisSession** _(Owner: Sara)_~~ **(Completed; ADR-001 Accepted)**  
   Scope: single session object, threading/reentrancy guarantees, `ns.*` shims, Runner/graph adapter contract, env-defaulting without hidden globals.

2. ~~**ADR-002 — Artifact immutability & manifest** _(Owner: Sara)_~~ **(Completed)**  
   Scope: episode directory layout, temp→atomic write policy, `manifest.json` schema (sizes + SHA256 + optional HMAC), ULID episode IDs, UUIDv5 directive/governance IDs, and `noesis artifacts verify` behavior.

3. ~~**ADR-003 — Schema governance & KPIs** _(Owner: Sara)_~~ **(Completed)**  
   Scope: per-file `$schema_version`, field-level stability flags, schema semver rules, mandatory migration notes, pinned KPI formulas (plan_adherence, tool_coverage, veto_count, success), and CI schema guard requirements.

4. ~~**Determinism Drill (tooling) PR** _(Owner: Sara)_~~ **(Completed)**  
   Deliverables: replay CLI (`diagnostics replay`) that re-runs an episode under `DeterminismConfig`, diffs artifacts/lineage with tolerances, emits clear DRIFT/NO DRIFT, and a named vetoed golden used by both CLI and CI. **Status:** CLI + comparer + goldens (minimal, veto, LLM) shipped; CI gate wired via `determinism-replay.yml`.

**Exit Criteria** ✅

- Every engineer can whiteboard an episode lifecycle (session → IDs → artifacts → manifest) without disagreement.
- Simulated vetoed action yields deterministic directive/governance IDs and manifest entries the team can follow step-by-step.
- Schema bumps cannot merge without an accompanying migration note template and reviewer checklist. (Met by ADR-003 guard.)
- Minimal-mode artifact pairs diff to zero when seeded identically; divergences are explained in the drill log. (Met by determinism drill tooling.)

---

### Phase 1 — Determinism Drill (DONE)

**Focus:** Ship the replay/drift UX on top of the deterministic runtime.

**Delivered**

- `diagnostics replay` CLI with structural/byte diffing (`noesis/cli/commands/diagnostics.py`, `noesis/diagnostics/replay.py`).
- Minimal-mode deterministic goldens + unit tests (`tests/golden/deterministic_run/run_{a,b}`, `tests/diagnostics/test_replay.py`).
- CI-enforced replay gate (`determinism-replay.yml` → `replay_gate.py`).
- Veto scenario golden (`tests/golden/veto_enforce/run_{a,b}`).

**Exit Criteria** ✅

- Minimal-mode artifacts are bit-for-bit identical across runs (covered by current goldens).
- Replay tool reports zero drift for goldens in CI.
- Governance lineage determinism validated by a vetoed golden.

---

### Phase 1.7 — Governance Modes (ADR-007 — DONE)

**Focus:** Make governance an explicit 3-mode faculty (**off / audit / enforce**) with canonical veto semantics and schema-governed signaling.

**Faculty order (canonical):** Intuition → Direction → Governance → Insight. Governance is **pre-act** and runs **after** Direction has produced a plan.

**Delivered**

- `GovernanceMode` enum: `OFF` (default), `AUDIT`, `ENFORCE` (`domain/faculties/governance.py`).
- `GovernanceFailurePolicy` enum: `FAIL_OPEN`, `FAIL_CLOSED` with `default_for(mode)` (audit → fail_open, enforce → fail_closed).
- Canonical episode outcome `vetoed`: in **enforce** mode, a pre-act veto terminates the episode immediately; **no Act event is emitted**.
- Governance event schema includes `mode`, `failure_policy`, `enforced`, `decision`, `policy_id`, `policy_version`, `policy_kind`, `rule_id`, `score`, `message`, `caused_by`, optional `details`, `error`.
- `fail_closed` treats policy failure/timeout as VETO with `error` metadata.
- Policy contract is pure: input (goal, plan), output `GovernanceResult`, no side effects.
- Tests (`tests/governance/test_pre_act.py`): off/audit/enforce coverage, enforce-veto termination, lineage wiring.
- Enforce-veto golden (`tests/golden/veto_enforce/`) wired into CI replay gate.

**Exit Criteria** ✅

- Governance mode/config defaults are explicit and test-backed.
- Episode-level outcome `vetoed` is canonical across `summary.json`, `state.json`, and terminate semantics.
- Governance events are schema-governed and lineage-linked; audit never blocks, enforce fail-fast blocks Act and terminates the episode.
- Determinism/replay gate includes at least one enforce-veto golden.

---

### Phase 1.8 — Action Candidates (ADR-008 — DONE)

**Focus:** Make side-effectful actions observable and governable before execution.

**Delivered**

- ActionCandidate data model and deterministic state hashing for pre-act gating (`domain/action_candidates.py`, `usecases/action_gating.py`).
- Pre-act governance wiring for governed actuation with action-candidate lineage (`infrastructure/actuation/default_actuation.py`, `usecases/actuation/governed_actuator.py`).
- Determinism fixtures covering allow/veto/fail-closed candidate flows (`tests/golden/adr_008/*`).

---

### Phase 1.9 — Dual Sync/Async Execution (ADR-009 — DONE)

**Focus:** Add first-class async execution without changing sync semantics.

**Delivered**

- Async solve path with preserved invocation order and failure semantics (`core.solve_async`, `usecases/episode_runner.py`).
- Async adapter actuator for awaitable results while keeping cognitive ownership in EpisodeRunner (`infrastructure/episode/adapter_actuator.py`).
- Tests covering async callables, async invoke/run, and error semantics (`tests/runtime/test_async_solve.py`).

---

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

### Phase 3 — Real LLM Example (DONE)

**Focus:** Prove real-world integration with a live LLM-backed flow.

**Delivered**

- LLM-backed example with recorded transcript (`tests/golden/llm_real/transcript.jsonl`).
- Full artifact suite emitted (events, state, summary, manifest) in `tests/golden/llm_real/run_{a,b}`.
- Wired into CI replay gate (`replay_gate.py` checks `llm-golden`).

**Remaining (Non-Blocking)**

- Add user-facing documentation on how to wrap external tools/graphs with Noēsis.

**Exit Criteria** ✅

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

## v1.0.0 = Architectural GA

Noēsis v1.0.0 is **architecturally complete**: deterministic cognitive loop, immutable artifacts, schema governance, and CI replay gates. It is a stable substrate for building cognitive agents.

What follows is **adoption completeness**: the integrations, ergonomics, and tooling that make Noēsis usable by teams without custom glue.

---

## Adoption Completeness (v1.1 → v1.3)

### Pillar 1 — Integration Spine (Providers + Tools)

First-class LLM provider adapters (OpenAI, Anthropic, local) with stable interfaces, retries/timeouts, and prompt provenance hooks. Tool runtime contract (subprocess, HTTP, MCP).

**Deliverables:**
- Stable provider interface + versioning policy
- Retries/timeouts/error mapping per provider
- Standardized prompt/provenance hooks
- Tool runtime contract (local subprocess, HTTP, MCP)

**Outcome:** Users can plug in OpenAI/Anthropic/local/whatever without writing custom glue.

---

### Pillar 2 — Adapter Coverage (LangGraph, CrewAI, etc.)

Minimal wrapper examples per ecosystem, canonical "how to integrate" docs, compatibility fixtures so adapters don't rot.

**Deliverables:**
- Minimal wrapper examples per ecosystem
- Canonical "how to integrate" docs
- Fixtures + compatibility tests (so adapters don't rot)

**Outcome:** Noēsis feels "everywhere" without becoming dependent on anything.

---

### Pillar 3 — Record → Replay → Diff UX

Polished CLI workflow: one command to record, one to replay+diff, clear drift explanations. Docs that show the workflow, not just the feature.

**Deliverables:**
- One command to record + label runs
- One command to replay + diff with clean output
- Drift explanation patterns ("what changed and why")
- Docs that show the workflow, not just the feature
- Governance docs: "Governance modes", "What veto means", failure policy semantics

**Outcome:** Artifacts become an everyday engineering loop (like tests), not a research artifact dump.

---

### Pillar 4 — Evals / Benchmarks / Dashboards

Opinionated eval runner, baseline suites (smoke/regression/behavior), local-first dashboard view.

**Deliverables:**
- Small, opinionated eval runner
- Baseline suites (smoke / regression / behavior)
- Basic dashboard view (even if local-first)

**Outcome:** Teams can justify adoption because they can measure cognition changes.

---

### Pillar 5 — Config + Deployment Story

Artifact storage backends (S3/GCS/local), team-friendly run indexing, hosted UI contract (even if "later").

**Deliverables:**
- Artifact storage backends (S3/GCS/local)
- Team-friendly run indexing / metadata
- Hosted UI story (define contract now, ship later)

**Outcome:** Noēsis becomes team-adoptable (shared storage, indexing, deployment contracts) without changing what it is: a cognitive framework.

---

## Future Exploration (v1.3+)

### Prompt Provenance & Cognitive Provenance (ADR-005)

- Expand coverage to all cognitive phases (add observe/act/learn paths).
- Wire prompt fingerprints into `events.jsonl` for direct joinability.
- Higher-level examples/notebooks for drift and incident analysis.
- Optional: per-field redaction/PII policies and adapter opt-ins.

### Meta-Cognition & Ecosystem Enhancements

- Meta-loop reflection and cognitive graph reasoning.
- TUI episode viewer, `noesis new-episode --danger-demo`, benchmarks expansion.
- Policy score canonicalization, runtime × schema × policy version matrix.

---

## Tech Debt & Intake (Ongoing Backlog)

- Document release freeze window ahead of GA to stabilize APIs.
- Convert staged drafts under `internal_docs/issue-drafts/` into GitHub issues with owners.
- Expand replay datasets under `benchmarks/` once the curriculum harness lands.
