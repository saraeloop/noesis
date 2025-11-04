# Noēsis Milestone Backlogs
**Program Increment:** v0.8 → v1.0  
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

## 1. Core Cognitive Loop Reinforcement
**Goal:** Make cognition causal, measurable, and extensible.  
**Aligned Research:** ReAct (Yao et al. 2022), Reflexion (Shinn et al. 2023)

| Task | Description | Layer | Status |
|------|--------------|--------|--------|
| Formalize cognitive verbs | Ensure Observe, Interpret, Plan, Act, Reflect, Learn are distinct event schemas with metrics | `domain/state/cognitive.py`, `trace/schema.py` | ✅ done (v0.7.0) |
| Add causal lineage | Link each event to its parent reasoning step (`caused_by`) | `domain/state/cognitive.py`, `usecases/episode_runner.py` | ✅ done (v0.7.0) |
| Cognitive clock | Add unified timestamps + phase durations for temporal cognition | `runtime/clock.py`, `usecases/episode_runner.py` | ✅ done (v0.7.0) |
| Meta-phase hooks | Pre/post hooks for governance or introspection | `usecases/hooks/meta_phase.py`, `usecases/episode_runner.py` | ✅ done (v0.7.0) |

---

## 2. Faculties Expansion
**Goal:** Solidify Intuition, Direction, Insight, and introduce Governance.  
**Aligned Research:** Tree of Thoughts (Yao et al. 2023), MetaGPT (2023)

| Faculty | Additions | Layer | Status |
|----------|------------|--------|--------|
| Intuition | Deterministic heuristic and LLM-based advisory shims | `domain/faculties/intuition.py` | ✅ done (v0.8.0) |
| Direction | Depth/beam-limited MetaPlanner with directive mutation + PlannerMode toggle | `domain/faculties/direction.py`, `domain/planner/meta.py` | ✅ done (v0.8.0) |
| Insight | Versioned per-episode KPIs persisted under `summary["insight"]["metrics"]` | `domain/faculties/insight.py` | ✅ done (v0.8.0) |
| Governance | Pre-act governor with audit/veto wiring and blocked ACT lineage | `domain/faculties/governance.py`, `usecases/episode_runner.py` | ✅ done (v0.8.0) |

### Risks
- Directive and governance identifiers remain ephemeral; stable IDs are needed for future `caused_by` links.
- `_apply_directive` surfaces terse errors, making directive/governance conflicts harder to debug.
- Minimal planner regression path still lacks coverage ensuring no direction/governance phases leak in legacy mode.

### Next Moves (ship as focused PRs)
1. Thread stable IDs through `PlannerDirective` / `GovernanceResult` and propagate them to downstream events.
2. Harden `_apply_directive` error reporting and governance keyword matching (word boundaries).
3. Add a minimal-mode regression test guaranteeing no governance/direction events appear when `PlannerMode=minimal`.
4. Expand docs and examples for governance auditing and planner tuning (README + docs site).

### Acceptance Checks
- Deterministic `PlannerDirective` diff captured in `tests/direction/test_meta_planner.py`.
- Governance ALLOW/AUDIT/VETO pathways block ACT and emit events (`tests/governance/test_pre_act.py`).
- Insight finalize produces versioned metrics that match goldens (`tests/insight/test_finalize_metrics.py`).
- Hook-order validator accepts documented retry sequences (`tests/runtime/test_hook_order.py`).
- LangGraph/adapter fixtures assert direction/governance phases (`tests/integration/test_cognitive_events.py`).

---

## v0.8 — Meta Planner & Governance
**Owner:** Core Runtime **Dependencies:** schema registry, planner config toggles

### ✅ Delivered in v0.8.0
- ✅ Depth/beam-limited `MetaPlanner` with `_apply_directive` mutations and PlannerMode toggle (`noesis/domain/planner/meta.py`, `noesis/domain/faculties/direction.py`).
- ✅ `PreActGovernor` gating ACT with audit/veto events and blocked direction lineage (`noesis/domain/faculties/governance.py`, `noesis/usecases/episode_runner.py`).
- ✅ Faculty schema registry, versioned JSON Schemas, and golden fixtures guarding payload contracts (`noesis/domain/faculties/versioning.py`, `noesis/trace/schema/`).
- ✅ Insight metrics builder emitting deterministic KPIs to `summary["insight"]["metrics"]` with versioned shapes (`noesis/domain/faculties/insight.py`).

### 📏 Acceptance Evidence
- `tests/direction/test_meta_planner.py` snapshots planner diffs deterministically.
- `tests/governance/test_pre_act.py` covers allow/audit/veto pathways and ACT blocking.
- `tests/insight/test_finalize_metrics.py` golden-matches insight metrics output.
- `tests/runtime/test_hook_order.py` validates the extended hook sequencing.
- `tests/integration/test_cognitive_events.py` exercises direction/governance phases end-to-end.

---

## v0.8 — Learning & Feedback
**Owner:** Learning Systems **Dependencies:** lineage artifacts (v0.7); diagnostics harness live

### Backlog
- Implement **`LearningPort`** (apply/revert/update_policy)
- Build **LearningOrchestrator** reacting to Reflect events
- Add **policy snapshot + diff**
- Extend CLI with `policy apply|revert`

### ✅ Acceptance Tests
- Two learning scenarios show ≥ 15 % policy score gain
- Rollback restores baseline ≤ 5 % deviation
- Each post-Reflect summary includes `policy_version` hash

---

## v0.9 — Shim retirement & episode UX
**Owner:** Core Runtime & DX  
**Dependencies:** governance schema merged; insight metrics stable (v0.8)

### ✅ Delivered in v0.9.0
- **Codemod:** `noesis migrate` rewrites deprecated shims to the stable surface with LibCST + TODO reporting.
- **Episode viewer:** `noesis view` renders KPIs, governance decisions, and validation warnings (plain + Rich renderers).
- **Shim removal:** legacy aliases disabled by default; temporary `NOESIS_LEGACY_SHIMS=1` escape hatch logs loud warnings.
- **Insight polish:** reflect-only wins count as success; phase durations clamp to ≥ 1 ms for deterministic KPIs.
- **Docs:** API surface reference + “Upgrading to v0.9” guide covering codemod flow and manual fixes.

### 📏 Acceptance Evidence
- `tests/tools/test_migrate.py` verifies codemod rewrites and idempotency.
- `tests/cli/test_viewer_plain.py` snapshots KPIs/phases; `tests/cli/test_viewer_utils.py` clamps durations.
- `tests/public/test_removed_symbols.py` + `tests/public/test_public_imports.py` enforce shim removal and env-guard reactivation.

### 🔜 Next
- Textual/TUI viewer (see v1.0 backlog) spawns from the CLI work.
- Direction ToT / governance benchmarking continues under the curriculum milestone.

---

## v1.0 — Curriculum, Meta-CoT & Release
**Owner:** Platform **Dependencies:** docs pipeline, schema freeze, CI signing keys

### 🔧 Backlog
- Implement **curriculum runner** → `curriculum.jsonl`
- Publish **docs site** with architecture + tutorials
- Freeze **schema/ports**, add version guard
- Implement **signed build CI/CD** path
- Integrate **Meta-CoT & Self-Discover** benchmarks into curriculum metrics
- Ship **Textual episode viewer (TUI)** behind `noesis[ui]` with timeline/metrics/governance panes
- Add **`noesis new-episode --danger-demo`** helper to seed sandbox runs for demos
- Draft **release notes** template covering migration table + viewer walkthrough

### ✅ Acceptance Tests
- Curriculum runs (smoke + regression + Meta-CoT) auto-compare outputs
- Reasoning-depth score ↑ ≥ 10 % between policy versions
- Docs deploy passes link + diagram checks
- Schema guard rejects incompatible events in CI
- Signed release verifies artifact attestations

---

## 📊 Measurable Outcomes by Capability

| Capability | Metric | Target |
|-------------|---------|---------|
| **Cognitive loop fidelity** | 99 % phase coverage; lineage ≥ 95 %; veto latency < 250 ms | ✅ |
| **Memory** | precision@3 ≥ 0.7; recall < 300 ms/query | ✅ |
| **Learning feedback** | +15 % policy gain; rollback ≤ 5 % deviation | ✅ |
| **Direction (ToT)** | ≥ 80 % success; avg branch ≤ 5; prune < 150 ms | ✅ |
| **Governance & Insight** | trust std dev < 0.1; drift recall ≥ 80 % | ✅ |
| **Curriculum & Meta-CoT** | regression 100 %; reasoning-depth +10 %; Docs ≥ 90; signatures verified | ✅ |

---

## ⚙️ Immediate Foundations (Cross-Cutting)

1. **CI / Testing Scaffolding**  
 • Unit + contract tests for all layers  
 • Diagnostics + schema validation in CI  
 • Coverage for `domain/`, `usecases/`, `interfaces/`

2. **Schema-Version Guardrails**  
 • Schema registry with version bump checks  
 • Lint rules block incompatibilities  
 • Snapshot diffing in diagnostics

3. **Shared Benchmark Harness**  
 **Owner:** Research Ops  
 • Datasets for episode replay, memory recall, learning feedback, ToT puzzles, governance sims  
 • Reused across milestones for reproducible metrics

---

## 🧭 Assessment Summary

| Observation | Impact |
|--------------|--------|
| Milestones 0.7–1.0 cover ReAct + Reflexion loops | ✅ Measurable reasoning cycles |
| Memory + curriculum (Voyager) create episodic continuity | ⚙️ FAISS dependency |
| Governance + diagnostics + schema guards → runtime-agnostic layer | ✅ |
| **Gap 1:** Tree-of-Thoughts / Self-Discover → Direction + Meta-CoT benchmarks | ✅ Closed |
| **Gap 2:** Legacy regression artifacts unlinked | ⚠️ Addressed below |

---

## 🧩 Regression Continuity Plan

**Objective:** Anchor v0.7+ metrics to historical Noēsis behavior for scientific reproducibility.

### 📦 Artifacts to Import
- v0.5–v0.6 episode traces (`events.jsonl`, `state.json`, `summary.json`)
- RuntimeContext logs and analyzer outputs
- SQLite memory snapshots + mock FAISS embeddings
- CLI transcripts from early faculty prototypes

### 🗓️ Schedule
| Phase | Deliverable | Target |
|-------|--------------|--------|
| **Week 1 (Pre-v0.7)** | Import and normalize legacy artifacts → `/benchmarks/regression/` | ✅ before FAISS build |
| **Week 2** | Write replay harness (`noesis diagnostics --replay`) | Blocks v0.7 testing |
| **Week 3** | Publish `/meta/reports/regression_baseline.md` | Baseline for CI comparisons |
| **Week 4** | Integrate into CI (auto-diff for lineage/timing/memory parity) | Before v0.7 freeze |

### 👥 Ownership
- **Primary:** Core Runtime (baseline import + schema alignment)
- **Support:** Research Ops (artifact curation + benchmark consistency)
- **Validation:** QA / Diagnostics (diff tooling + CI integration)

### ✅ Success Criteria
- Regression datasets validated before v0.7 execution
- CI replay passes: lineage ≥ 95 %, duration ± 5 %, recall precision@3 ≥ 0.7
- Any drift auto-surfaced in CI summary

---
