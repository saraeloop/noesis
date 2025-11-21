# ADR-005 — Prompt Provenance as Cognitive Runtime Artifact

- **Status:** Proposed (Experimental, behind feature flag)  
- **Date:** 2025-11-21  
- **Owner:** Sara Loera (@saraeloop)  
- **Reviewers:** Core Engineering, Runtime/Infra, Research  
- **Related roadmap items:** ADR-001, ADR-002, ADR-003, ADR-004, ADR-006 (“Replay & Drift Tooling”)  
- **Release impact:** Non-blocking for v1.0.0; shipped as an opt-in, experimental feature and matured in v1.1+.

---

## 1. Context

ADR-001/002/003/004 establish Noēsis as a cognitive runtime with:

- **Structured sessions** and episode IDs (ADR-001).
- **Integrity-preserving artifacts** (`events.jsonl`, `summary.json`, `state.json`, `learn.jsonl`, `manifest.json`) (ADR-002).
- **Schema governance & KPI pinning** (ADR-003).
- **Deterministic replay** under `DeterminismConfig` (ADR-004).

Together, these make the *cognitive loop* observable:

> OBSERVE → INTERPRET → PLAN → (GOVERNANCE) → ACT → REFLECT → LEARN

Each phase emits entries into `events.jsonl` and updates `state.json` / `summary.json`. That gives us a structured view of:

- what the system did, and  
- how it evaluated itself.

What remains opaque is the **prompt layer** — the natural-language “code” used to drive cognition:

- system prompts  
- planner templates  
- reflection / learning prompts  
- governance / veto prompts  
- tool-calling prompts  
- meta-prompts and scaffolding  

In practice:

- These prompts **encode agent behavior**.  
- They are **tuned and evolved** like code and policies.  
- They are rarely **stored, versioned, or linked to outcomes** in a structured way.

Provenance work (e.g. W3C PROV, ProvONE, and prompt provenance proposals) treats such “reasoning inputs” as first-class entities: you don’t just know *what* was concluded, but *which prompt stack* and *which actors* led there.

Noēsis already covers workflow-style provenance (episodes, phases, metrics, artifacts). What’s missing is a first-class, runtime-centric view of the **prompts actually used during cognition**, so that engineers and researchers can answer questions like:

- “Which planner prompt was active when this episode hallucinated?”  
- “Which reflection prompt correlates with better tool success?”  
- “What exact prompt stack did this episode run under, phase by phase?”

Noēsis’s mission is **“cognition made observable.”** If prompts are the *language of cognition* for agents, then prompt usage during a run should become part of the cognitive trace — under the same schema and integrity discipline as other artifacts — **without** turning Noēsis into a full prompt registry or UI.

---

## 2. Decision

Introduce **Prompt Provenance** as an **optional, schema-governed, determinism-friendly runtime artifact**:

> Capture the prompts actually used during an episode’s cognitive phases and link them to episodes, events, and outcomes.

This is done via:

1. A new **optional** artifact: `prompts.jsonl`.  
2. A small **PromptRecorder** utility in the runtime/trace layer.  
3. Minimal wiring from core-controlled LLM call sites, keeping the feature behind a config flag.

### 2.1 New artifact: `prompts.jsonl` (optional, experimental)

- When enabled, each episode **may** emit a `prompts.jsonl` file alongside:
  - `events.jsonl`, `summary.json`, `state.json`, `learn.jsonl`, `manifest.json`.
- `prompts.jsonl` is **line-oriented JSON**; each line is one prompt record.
- The artifact is governed by ADR-003:
  - Each record includes schema metadata:
    - `"$schema_name": "prompt"`
    - `"$schema_version": "1.0.0"` (initial).
  - Schema source lives in `internal_docs/schema/prompt.yaml` and is generated into `docs/schema/prompt.schema.json`.
  - All fields begin as `stability: experimental`.

Prompt provenance is **opt-in** and controlled by configuration, e.g.:

- `prompt_provenance_enabled: bool`  
- `prompt_provenance_mode: "full" | "hash_only" | "redacted"`

### 2.2 Prompt record schema (v1, experimental)

Each prompt record is a single JSON object written on one line in `prompts.jsonl`.

**Identity & schema**

- `"$schema_name": "prompt"`  
- `"$schema_version": "1.0.0"`  
- `episode_id: str`  
  - Episode this prompt belongs to; matches `state.json` / `summary.json`.
- `event_id: str | null`  
  - Cognitive event ID this prompt is associated with (if any; matches `events.jsonl`).
- `outcome_event_id: str | null`  
  - Optional event ID corresponding to the model’s response or outcome.

**Cognitive context**

- `phase: "observe" | "interpret" | "plan" | "governance" | "act" | "reflect" | "learn"`  
  - Required; matches cognitive phases already used in `events.jsonl`.
- `agent_id: str`  
  - Logical identifier for the emitting faculty/policy/adapter (e.g. `direction.planner`, `intuition`, `governance.pre_act`, `adapter:demo`).

**Prompt content & structure**

- `role: str | null`  
  - LLM role, if applicable (`system`, `user`, `assistant`, `tool`, etc.).
- `kind: str`  
  - High-level purpose within the phase, e.g.:
    - `system`, `reasoning`, `reflection`, `tool_call`, `governance`, `meta`, `insight`.
- `template_id: str | null`  
  - Optional logical ID/name of the template (e.g. `planner_v2`, `reflect_v1`).
- `template: str | null`  
  - Template text before variable substitution; nullable.
- `rendered: str`  
  - Final prompt text sent to the model (post substitution / concatenation).
- `variables: dict[str, object] | null`  
  - Dynamic variables used to render the template, if reasonably serializable and not sensitive.

**Provenance, determinism & model info**

- `fingerprint: str`  
  - Deterministic hash of the normalized `rendered` prompt (e.g. `sha256:<hex>`).
- `timestamp: str`  
  - When the prompt was rendered (ISO-8601). Under `DeterminismConfig`, derived from the deterministic clock.
- `model: str | null`  
  - Model identifier, if available (e.g. `gpt-4.1`, `claude-3.5-sonnet`).

**Privacy mode & deployment context**

- `mode: "full" | "hash_only" | "redacted"`  
  - `full`: store `template`, `rendered`, `variables`.  
  - `hash_only`: only metadata + `fingerprint`; omit prompt text and variables.  
  - `redacted`: store prompt fields after an optional redaction policy.
- `tags: dict[str, str] | null`  
  - Optional deployment/environment tags mirroring `episode.tags` (e.g. `{ "env": "prod", "tenant": "acme" }`).

All v1 fields are marked `experimental` in the schema registry but still governed by ADR-003 (versioning, migrations, tests).

### 2.3 Join story: prompts ↔ events ↔ state ↔ summary

`prompts.jsonl` is designed to **join cleanly** with existing artifacts:

- `episode_id` ↔ `summary.json` / `state.json` / `events.jsonl` / `learn.jsonl` / `manifest.json`.  
- `event_id` / `outcome_event_id` ↔ specific entries in `events.jsonl`.  
- `phase` ↔ cognitive phases in `events.jsonl`.

In a later iteration, `events.jsonl` **may** gain a `prompt_fingerprint` field to allow direct lookups from events into the prompt corpus, but this ADR does **not** require it.

### 2.4 Prompt recorder & integration points

Introduce a small runtime utility, e.g. `PromptRecorder`, in the trace/runtime layer.

**Responsibilities:**

- Lazily open `prompts.jsonl` under `runs/<label>/<episode_id>/`.  
- Normalize `rendered` before hashing (whitespace, line endings).  
- Compute `fingerprint` and inject:
  - schema metadata,  
  - `episode_id`, `phase`, `agent_id`,  
  - `timestamp` (from configurable clock),  
  - `mode` and `tags`.  
- Respect:
  - `prompt_provenance_enabled`,  
  - `prompt_provenance_mode`.

When disabled, `PromptRecorder` is effectively a **no-op** and `prompts.jsonl` is never created.

**Initial integration scope (minimal):**

- Only at **Noēsis-owned LLM call sites**, e.g.:
  - Intuition (INTERPRET).  
  - Planner / direction (PLAN).  
  - Governance (GOVERNANCE).  
  - Reflection (REFLECT).  
- Only when:
  - We have access to the rendered prompt, and  
  - The integration cost is low (no heavy refactors).

Adapters (e.g. LangGraph wrappers, MCP observers) **may** opt-in later by calling into `PromptRecorder` explicitly.

### 2.5 Determinism & ADR-004 alignment

Under `DeterminismConfig`:

- `PromptRecorder` should use:
  - the deterministic clock for `timestamp`, and  
  - a stable hash function for `fingerprint`,  
  - predictable ordering driven by the existing cognitive loop.

For v1 (experimental):

- Deterministic tests may assert that **simple minimal-mode scenarios** produce identical `prompts.jsonl` under the same deterministic configuration.  
- Replay *correctness* for ADR-004 remains defined by:
  - `events.jsonl`, `state.json`, `summary.json`, `manifest.json`.  
- `prompts.jsonl` is treated as an **observational artifact** that is “determinism-friendly” but **not** part of the hard replay gate for v1.0.0.

A future ADR may promote `prompts.jsonl` to a required replay surface once schema and coverage stabilize.

### 2.6 Scope boundaries

Noēsis will **not**:

- Act as a prompt registry or version control system.  
- Provide UI for prompt editing, diffing, ranking, or collaboration.  
- Attempt to define global “prompt taxonomies” beyond the minimal `kind` and `phase` fields.

Noēsis will:

- Treat prompts as **runtime cognitive artifacts**: things that happened during a run.  
- Expose them as structured, joinable data for:
  - external research tools,  
  - governance dashboards,  
  - drift analysis,  
  - separate “PromptHub for Noēsis”-style projects.

### 2.7 Implementation scope (v0.1, 1.0.0 timeframe)

This ADR defines the full Prompt Provenance direction, but the **initial implementation** for v1.0.0 will intentionally be narrow:

- `prompts.jsonl` is **optional** and gated by config:
  - `prompt_provenance_enabled`,
  - `prompt_provenance_mode` (supporting `full` and `hash_only` only).
- v0.1 will capture a minimal field set:
  - `episode_id`, `phase`, `agent_id`, `rendered`, `fingerprint`,
    `timestamp`, `model`, `mode`.
- v0.1 will be wired only into a small set of Noēsis-controlled LLM call sites:
  - Planner / Direction (PLAN),
  - Act (ACT),
  - optionally Governance (GOVERNANCE) where trivial to add.
- Determinism:
  - at least one minimal deterministic scenario will assert identical
    `prompts.jsonl` under the same `DeterminismConfig`.

The **richer schema surface** (templates, variables, redaction policies, more phases) and **deep schema_guard integration** are intentionally deferred to **v1.1+** once we have usage feedback. Those changes may be captured in follow-up ADRs or revisions.

---

## 3. Consequences

### Benefits

**For researchers**

- Can correlate **prompt patterns with behavior**:
  - hallucinations vs. success,  
  - planner variants vs. tool success,  
  - governance prompt evolution vs. veto patterns.  
- Can extract prompt corpora from Noēsis runs without bespoke logging hacks.  
- Can align with provenance work by treating prompts as entities in a cognitive provenance graph.

**For engineers**

- Can answer:
  - “What prompt stack actually ran in episode X?”  
  - “Which `template_id` and `fingerprint` were active in this incident?”  
- Can attach prompt fingerprints to incident reports / replay scenarios.  
- Can build external prompt explorers and debuggers **on top of** Noēsis artifacts, rather than baking UI into core.

**For Noēsis**

- Deepens Noēsis’s identity as a **cognitive provenance framework**:

  > Not just *what* cognition did, but *what language* it used to think.

- Stays aligned with prior provenance work (entities, activities, agents) without adopting a full PROV stack.

### Costs / risks

- **Schema maintenance**
  - `prompts.jsonl` needs:
    - schema YAML + generated JSON schema,  
    - `stability` metadata,  
    - migration notes for breaking changes (ADR-003 discipline).  

- **Runtime overhead**
  - Extra hashing and file I/O per prompt.  
  - Must be cheap to disable; default for many deployments may be `hash_only` or entirely off.

- **Security / privacy**
  - Prompts can contain user data and secrets.  
  - Teams must choose `mode` and redaction policies appropriate to their risk profile.

---

## 4. Alternatives considered

1. **Do nothing (keep prompts implicit).**  
   - Pros: zero overhead, no new schema surface.  
   - Cons: agents stay “black box” at the prompt layer; hard to debug; diverges from provenance direction.

2. **Make Noēsis a full prompt registry/versioning system.**  
   - Pros: would centralize prompt management and history.  
   - Cons: out of scope for Noēsis; conflates runtime observability with configuration and product-level UX.

3. **Embed prompts directly into `events.jsonl` only.**  
   - Pros: fewer artifacts; events remain the single source of truth.  
   - Cons:
     - bloats the event log with large prompt bodies,  
     - couples prompt evolution tightly to event schemas,  
     - makes prompt-centric analysis harder and more brittle.

4. **Record only final LLM prompts, ignore governance/meta prompts.**  
   - Pros: simpler; fewer call sites.  
   - Cons: governance, reflection, and learning prompts are often *the* reason a system behaves the way it does; omitting them defeats the point of cognitive provenance.

---

## 5. Acceptance criteria

ADR-005 is considered *implemented (experimental)* when:

1. **Artifact exists & is wired**
   - When `prompt_provenance_enabled` is true:
     - `prompts.jsonl` is created in `runs/<label>/<episode_id>/`.  
     - Each line is a valid JSON object conforming to v1 prompt schema:
       - includes `"$schema_name": "prompt"`, `"$schema_version": "1.0.0"`,  
       - includes `episode_id`, `phase`, `agent_id`, `fingerprint`, `mode`.

2. **Linkage works**
   - For at least one example scenario:
     - `episode_id` matches other artifacts,  
     - `event_id` / `outcome_event_id` (when present) link to `events.jsonl`,  
     - `phase` aligns with cognitive phases in `events.jsonl`.

3. **Opt-in behavior is clear**
   - Prompt provenance can be toggled via config/env/session.  
   - At least two modes work:
     - `full`  
     - `hash_only`  
   - When disabled, the recorder is a no-op and `prompts.jsonl` is not created.

4. **Determinism compatibility (smoke level)**
   - Under `DeterminismConfig`, a small deterministic scenario:
     - produces identical `prompts.jsonl` bytes across two runs, **or**  
     - is explicitly documented as “observational-only” if determinism is not guaranteed yet.  
   - A test (e.g. `tests/runtime/test_prompt_provenance.py`) covers this behavior.

5. **Schema governance**
   - `internal_docs/schema/prompt.yaml` exists and is registered in the schema index.  
   - Generated JSON schema is in `docs/schema/prompt.schema.json`.  
   - Schema guard validates prompt fixtures in CI.  
   - Breaking changes require:
     - version bump,  
     - migration note,  
     - updated tests.

6. **Minimal docs**
   - `prompts.jsonl` is documented as **experimental** in:
     - artifact overview (`runs/README.md` / internal docs),  
     - developer docs,  
     - with explicit discussion of:
       - modes (`full`, `hash_only`, `redacted`),  
       - privacy/PII implications.

---

## 6. Migration plan

1. **Define schema**
   - Add `internal_docs/schema/prompt.yaml` with fields from §2.2:
     - mark all as `stability: experimental`,  
     - `since: 1.0.0`.  
   - Extend the schema generator to emit `docs/schema/prompt.schema.json` and register it.

2. **Introduce `PromptRecorder`**
   - Implement runtime utility to:
     - open/manage `prompts.jsonl`,  
     - normalize `rendered` and compute `fingerprint`,  
     - inject metadata (`episode_id`, `phase`, `agent_id`, `timestamp`, `mode`, `tags`),  
     - respect `DeterminismConfig` when provided.  
   - Provide a trivial no-op implementation for the disabled case.

3. **Wire into core call sites**
   - Start with Noēsis-controlled LLM calls:
     - Intuition, planner/direction, governance, reflection.  
   - Capture at least:
     - `episode_id`, `phase`, `agent_id`, `role`, `kind`, `rendered`, `fingerprint`, `timestamp`, `mode`.

4. **Add tests**
   - Add tests that:
     - exercise prompt recording in a minimal deterministic scenario, and  
     - validate schema compliance for sample records.

5. **Document**
   - Update artifact and developer docs to include:
     - `prompts.jsonl` description,  
     - join patterns with `events.jsonl` / `state.json` / `summary.json`,  
     - configuration flags and modes.  
   - Add ADR-005 to the ADR index and reference from replay/drift plans (ADR-006).

6. **Collect feedback**
   - Share v1 with early research/platform users to gather:
     - which fields are actually useful,  
     - performance / storage impact,  
     - privacy expectations.  
   - Plan any v1.1+ schema updates through ADR-003 governance.

---

## 7. Open questions / risks

- **Scope of capture**
  - Do we limit to core cognitive phases, or also capture outer UI/system prompts?  
  - How do we treat nested tool-generated prompts (e.g. MCP tools that themselves prompt models)?

- **Privacy / compliance**
  - Do we eventually need per-field redaction or PII classification?  
  - How do tenants control which prompts are retained vs. hashed-only?

- **Storage & retention**
  - For large deployments, how long is `prompts.jsonl` retained?  
  - Do we support rotation/compaction in core, or expect downstream systems to manage it?

- **Schema evolution**
  - How often will the schema change as new agent patterns appear?  
  - When do fields graduate from `experimental` → `beta` → `stable`?

- **Replay semantics**
  - If prompts become a stronger part of replay semantics later, what guarantees (if any) do we give about replaying with historical prompts vs. just analyzing them?

---

## 8. References

**Internal**

- ADR-001 — Runtime Session  
- ADR-002 — Artifact Integrity & Manifest  
- ADR-003 — Schema Governance & KPIs  
- ADR-004 — Runtime Determinism & Replayability  
- ADR-006 — Replay & Drift Tooling (planned)  
- `noesis/trace/schema/*`  
- `noesis/runtime/determinism.py`  
- `noesis/runtime/session.py`

**External / prior art**

- W3C PROV family (PROV-DM, PROV-O, PROV-PRIMER) — provenance of entities, activities, and agents.  
- ProvONE / ProvONE+ — extensions of PROV for workflows and executions.  
- Prompt provenance research (e.g. PROV-style models for prompts + completions).  
- Prompt-oriented tools like PromptAid — visual analytics and testing over prompt templates and metrics.

Noēsis builds on these ideas by treating prompts as **runtime cognitive artifacts** tied to explicit cognitive phases (observe/interpret/plan/governance/act/reflect/learn) and integrating them into a schema-governed artifact suite suitable for replay analysis, drift detection, and governance in cognitive systems.