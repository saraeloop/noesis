# 🧠 Noēsis Milestone Backlogs
**Program Increment:** v0.7 → v1.0  
**Audience:** Core Engineering, Research, and QA

---

## 🌌 Vision

Noēsis is a **cognitive framework** — not a workflow engine, not a chat orchestrator.  
It formalizes reasoning as a *structured cognitive process* that is **observable, extensible, and testable**.

> “We build like engineers. We reason like researchers.”  
> Noēsis bridges software architecture and cognitive science — aligning rigor from insights like **ReAct**, **Reflexion**, **Voyager**, **Tree of Thoughts**, **Self-Discover**, and **Meta-CoT**.

Every update strengthens three dimensions:
- **Cognitive fidelity:** Observe → Interpret → Plan → Act → Reflect → Learn
- **Architectural purity:** clear domain boundaries, dependency inversion, zero side effects
- **Framework agnosticism:** interoperable with LangGraph, CrewAI, OpenDevin, MCP, etc., but dependent on none.

---

## 🧩 1. Core Cognitive Loop Reinforcement
**Goal:** Make cognition causal, measurable, and extensible.  
**Aligned Research:** ReAct (Yao et al. 2022), Reflexion (Shinn et al. 2023)

| Task | Description | Layer | Status |
|------|--------------|--------|--------|
| Formalize cognitive verbs | Ensure Observe, Interpret, Plan, Act, Reflect, Learn are distinct event schemas with metrics | `domain/state`, `trace/schema` | ✅ partial |
| Add causal lineage | Link each event to its parent reasoning step (`caused_by`) | `domain/state/models.py` | ⏳ |
| Cognitive clock | Add unified timestamps + phase durations for temporal cognition | `runtime/_summary.py` | ⏳ |
| Meta-phase hooks | Pre/post hooks for governance or introspection | `usecases/episode_runner.py` | ⏳ |

---

## 🧠 2. Faculties Expansion
**Goal:** Solidify Intuition, Direction, Insight, and introduce Governance.  
**Aligned Research:** Tree of Thoughts (Yao et al. 2023), MetaGPT (2023)

| Faculty | Additions | Layer | Status |
|----------|------------|--------|--------|
| Intuition | Add probabilistic and LLM-based inference adapters | `domain/faculties/intuition.py` | ⏳ |
| Direction | Expand planner for meta-planning + success-based weighting | `domain/faculties/direction.py` | ⏳ |
| Insight | Enable cross-episode metrics + drift detection | `domain/faculties/insight.py` | ⏳ |
| Governance | Introduce veto/trust hooks, enforce ethical constraints | `domain/faculties/governance.py` | 🔴 new |

---

## 🚀 v0.7 — Memory & Loop Fidelity
**Owner:** Core Runtime **Dependencies:** event schema draft, FAISS toolchain

### 🔧 Backlog
- Ship **FAISS adapter** with full SQLite parity
- Implement **`caused_by` lineage propagation** across all six verbs
- Add **RuntimeClock instrumentation** (phase durations)
- Wire **diagnostics schema validation** into CI

### ✅ Acceptance Tests
- Replay 10 episodes → 100 % verbs emit durations ± 5 % variance
- Lineage coverage ≥ 95 % with valid `caused_by`
- Memory recall retrieves ≥ 3 facts/query (no timeouts)
- `noesis diagnostics` exit 0; schema drift fails diff

---

## 🧠 v0.8 — Learning & Feedback
**Owner:** Learning Systems **Dependencies:** lineage artifacts (v0.7); diagnostics harness live

### 🔧 Backlog
- Implement **`LearningPort`** (apply/revert/update_policy)
- Build **LearningOrchestrator** reacting to Reflect events
- Add **policy snapshot + diff**
- Extend CLI with `policy apply|revert`

### ✅ Acceptance Tests
- Two learning scenarios show ≥ 15 % policy score gain
- Rollback restores baseline ≤ 5 % deviation
- Each post-Reflect summary includes `policy_version` hash

---

## ⚖️ v0.9 — Governance, Insight & Direction
**Owner:** Safety, Insight & Reasoning  
**Dependencies:** governance schema merged; learning metrics emitted; **Direction ToT success metrics running in diagnostics (governance work MUST wait until this gate passes)**

### 🔧 Backlog
- Define **GovernancePolicy contract** + evaluation semantics
- Implement **veto/trust loop**, emit `governance.audit|veto`
- Build **InsightAggregator** for cross-episode KPIs
- Expand **Direction** for **Tree-of-Thoughts** multi-hypothesis reasoning with heuristics + pruning

### ✅ Acceptance Tests
- Veto blocks unsafe action → no downstream side effects
- `diagnostics --governance` trust ratio ≥ 0.7
- `insight --trend` computes drift < 8 min on 20 episodes
- **Direction (ToT)** benchmarks: ≥ 80 % success (↑ from 60 %), branch depth metrics ≤ 5 % variance

---

## 📘 v1.0 — Curriculum, Meta-CoT & Release
**Owner:** Platform **Dependencies:** docs pipeline, schema freeze, CI signing keys

### 🔧 Backlog
- Implement **curriculum runner** → `curriculum.jsonl`
- Publish **docs site** with architecture + tutorials
- Freeze **schema/ports**, add version guard
- Implement **signed build CI/CD** path
- Integrate **Meta-CoT & Self-Discover** benchmarks into curriculum metrics

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



