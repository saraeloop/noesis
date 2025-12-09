# Changelog

## Unreleased
- Internal: Core orchestration split into `_run_minimal_episode` and `_run_adapter_episode` with shared finalization and runner-port wiring for determinism (behavior and artifacts unchanged).
- Use-case ports added (`noesis/usecases/ports.py`) and `EpisodeRunner` refactored to depend on ports; import-linter contracts now enforce `usecases` isolation from adapters/CLI (ADR-006).

## v1.1.0 – 2025-12-08
### Added
- Prompt provenance v1.1 (ADR-005): schema-governed `prompts.jsonl` (`$schema_name: prompt`, `$schema_version: 1.1.0`), fixtures, and schema guard.
- PromptRecorder modes: `full`, `hash_only`, `redacted` with deterministic hashing, redaction, tags, templates, and variables; manifest integration and leakage guards.
- Multi-phase prompt coverage: interpret (intuition), plan (direction.planner), governance (governance.pre_act), reflect (reflect), with tag threading and optional event linkage.
- Replay diagnostics: `noesis diagnostics replay` CLI and `noesis.diagnostics.compare_runs` with deterministic goldens and unit tests.

### Notes
- Prompt provenance remains experimental and opt-in; adapters/UI and per-field PII policies are out of scope.
- Vetoed golden + CI replay gate, real LLM example, and threading/ownership tests remain on the roadmap.

## v1.0.0 – 2025-11-21
### Highlights
- Runtime ownership (ADR-001) is GA: `NoesisSession`/`SessionBuilder` + `DefaultSessionProvider` back all `ns.*`/CLI entrypoints, with determinism plumbed through sessions.
- Determinism substrate and drill (ADR-004): canonical JSON writers, deterministic clock/RNG/ULID/UUID lineage, and replay comparator CLI (`noesis diagnostics replay`) backed by deterministic goldens.
- Artifact immutability (ADR-002) + schema governance (ADR-003) remain enforced; manifests, summary/state/events stay canonical with atomic writes.
- CLI gains replay diagnostics and retains artifacts verification; tests guard structural determinism and replay drift.
- Prompt provenance (ADR-005) shipped as experimental/opt-in: prompt schema 1.1.0, `PromptRecorder` with `full`/`hash_only`/`redacted`, multi-phase coverage, and schema-guarded fixtures/tests.

### Notes
- Prompt Provenance (ADR-005) is experimental/opt-in (`prompt@1.1.0`) and not part of the replay gate.
- Existing `ns.run/solve/set` shims delegate to sessions; migrate code incrementally by constructing explicit sessions where needed.

## v0.9.5 – 2025-11-04
### Breaking Changes
| Removed | Replacement | Codemod rule |
| --- | --- | --- |
| `noesis.summary.load` | `noesis.summary.read` | `summary.load` |
| `noesis.summary.finalize_summary` | `noesis.summary.finalize` | `summary.finalize` |
| `noesis.events.*_event` helpers | `noesis.events.start/observe/…` | `events.*_event` |
| `noesis.state.store.EpisodeStore` | `noesis.episode.EpisodeIndex` | `state.store` |

> Use `noesis migrate` to apply the codemod. The tool prints `{renamed, replaced, skipped}` counts and TODO files that still reference removed symbols.

### Added
- `NoesisSession` ownership model with `ns.session_provider()`, `noesis.create_session(...)`, and CLI wiring so orchestrators can safely pin configs/ports per session (ADR-001).
- End-to-end artifact immutability: ULID episode IDs, deterministic directive/governance UUIDv5 helpers, atomic writers, `manifest.json` with optional HMAC signatures, and the `noesis.artifacts` public API + `noesis artifacts verify` CLI (ADR-002).
- `noesis migrate` codemod with JSON/pretty output, TODO summaries, and `--dry-run` for safe previews.
- `noesis view` CLI viewer showing episode header, KPIs, governance decisions, and a humanised timeline (`--grep`, `--json`, `--events`, `--fail-on-invalid`).
- Legacy escape hatch `NOESIS_LEGACY_SHIMS=1` (prints a prominent warning) to temporarily re-enable removed APIs for one patch release.

### Notes
- `noesis.state.store` now raises `ImportError` unless the legacy env flag is set; import `EpisodeIndex` from `noesis.episode`.
- Validation helpers highlight schema issues as `file schema:label → $.pointer message`. Pass `--fail-on-invalid` to make the viewer exit non-zero when violations exist.
- Optional extras keep the base install lean: `pip install noesis[migrate]` for the codemod and `noesis[ui]` for Rich/Textual viewer enhancements.

## v0.8.0 – 2025-11-12
### Added
- Depth- and beam-limited `MetaPlanner` plus `_apply_directive` support land as the default planner (toggled via `PlannerMode` or `NOESIS_PLANNER`).
- `PreActGovernor` introduces governance veto/audit events and blocks ACT on `veto`, emitting `direction(status=blocked)` for lineage clarity.
- Faculty schema registry, versioned JSON Schemas, and golden fixtures keep Intuition, Direction, Governance, and Insight payloads auditable.
- Deterministic heuristic and LLM intuition shims provide advisory behaviour that can be exercised in tests without remote calls.
- Insight summaries now expose versioned per-episode metrics (`phase_ms`, `veto_count`, `plan_revisions`, `plan_adherence`, `tool_coverage`, `success`) under `summary["insight"]["metrics"]`.
- Event bus writers for `direction` and `governance` phases ensure downstream observers receive the enriched cognitive loop.

### Changed
- EpisodeRunner threads the meta planner and pre-act governance through the cognitive pipeline (`observe → interpret → plan → direction → governance → act/blocked → reflect → finalize`) while preserving causal IDs.
- Configuration snapshots capture the new planner mode, and the runtime honors `NOESIS_PLANNER=minimal` as the opt-out path.
- Hook-order validation now tolerates the extended loop and leverages the shared schema registry.

### Tests
- Added golden and contract suites for the faculty schemas, planner diffs, governance veto/audit coverage, deterministic insight finalization, minimal-mode smoke runs, schema round-trips, and adapter/event goldens.

### Breaking / Behavior Changes
- **Default planner mode is now `meta`**, which **enables pre-ACT governance**. To retain legacy behavior:
  - Env: `NOESIS_PLANNER=minimal`
  - Code: `ns.set(planner_mode="minimal")`

### Upgrade Notes
- New `direction` and `governance` events appear in traces. Downstream tooling should:
  - Treat unknown phases as no-ops, or handle:
    - `direction.payload.status ∈ {applied, skipped, blocked}`
    - `governance.payload.decision ∈ {allow, audit, veto}`
- Insight metrics moved to `summary["insight"]["metrics"]`. Example:
  ```python
  s = ns.summary.read(eid)
  insight = s["insight"]["metrics"]  # {phase_ms, veto_count, plan_revisions, branching_factor, plan_adherence, tool_coverage, success}

### Compatibility
| Faculty | Schema version | Compatible until |
|---------|----------------|------------------|
| Intuition | 1.0.0 | All 1.x releases |
| Direction | 1.0.0 | All 1.x releases |
| Governance | 1.0.0 | All 1.x releases |
| Insight | 1.0.0 | All 1.x releases |

## v0.7.1 – 2025-11-02
### Added
- Long-term memory persistence pipeline: episode summaries now feed memory ports declaring the `long_term_memory` capability, with dedicated `memory` events for observability.
- Built-in SQLite-backed memory adapter (`noesis.infrastructure.memory.SQLiteMemory`) for easy persistent knowledge bases in development and testing.
- Public facades and top-level imports (`noesis.context`, `noesis.events`, `noesis.summary`, `noesis.learn`, `noesis.runtime.*`) plus a documented API surface page covering supported imports.

### Changed
- README documents the cognitive framework in depth and showcases the new persistent memory workflow.
- Episode index moved behind a dedicated port; import `EpisodeIndex` from `noesis.episode` (legacy `noesis.state.store` emits a deprecation warning and will be removed in v0.8.0).

### Deprecated
- `noesis.runtime._events`, `noesis.runtime._summary`, `noesis.runtime._learning`, and `noesis.runtime._utils` now emit deprecation warnings and will be removed in **v0.9.0**. Import from `noesis.events.read/start`, `noesis.summary.finalize/read`, `noesis.learn.emit`, and `noesis.runtime.utils` respectively.

## v0.7.0 – 2025-11-01
### Added
- Cognitive loop primitives — `CognitiveVerb`, `CognitiveEvent`, and `LineageTracker` — formalise the six verbs with immutable payloads and causal IDs (`noesis/domain/state/cognitive.py`).
- High-resolution `RuntimeClock` instrumentation wraps each verb, producing per-phase latency metrics consumed by diagnostics (`noesis/runtime/clock.py`).
- Event emission adapters (`noesis/runtime/events_emitter.py`) and meta-phase hooks (`noesis/usecases/hooks/meta_phase.py`) enable governance and observability extensions without touching orchestration.
- Integration and unit tests cover lineage coverage, timing sanity, and enriched episode artifacts (`tests/domain/test_cognitive_lineage.py`, `tests/runtime/test_clock.py`, `tests/integration/test_cognitive_events.py`).

### Changed
- `EpisodeRunner` now seeds lineage, times each verb, and emits metric-rich `events.jsonl` entries while enforcing learn-phase payload contracts (`noesis/usecases/episode_runner.py`).
- `RuntimeEventBus` cooperates with the new instrumentation to avoid double emission and preserve causal chains (`noesis/interfaces/observability.py`).
- Trace schema bumped to **1.2.0** with validation for `metrics` and `caused_by`; legacy helpers mint stable IDs (`noesis/trace/schema.py`, `noesis/trace/events.py`, `noesis/runtime/_events.py`).
- `core.run` wires shared clock/lineage/emitter instances so minimal mode benefits from the reinforced loop (`noesis/core.py`).

### Removed
- Minimal actuator no longer emits reflect events directly; loop emissions are centralised in the runner (`noesis/domain/planner/minimal.py`).

## v0.6.1 – 2025-10-31
### Changed
- Runtime “container” terminology is now `RuntimeContext`, aligning APIs (`run`, `solve`, `summary`, CLI commands) and helpers (`create_runtime_context`, `load_runtime_context`) around a cognition-focused metaphor.
- Documentation, release checklists, and tests now reference contexts, clarifying how to pass custom runtime minds through CLI and Python surfaces.

### Removed
- Legacy CLI plumbing (`noesis.cli.container`) was replaced with `noesis.cli.runtime_context`.

## v0.6.0 – 2025-10-30
### Added
- Domain-level `ConfigSettings` value object with validated overrides ensuring config diffs remain declarative (`noesis/domain/config/settings.py`).
- CI-oriented diagnostics: `noesis diagnostics --strict` now validates port contracts, redacts secrets, and emits machine-readable JSON (`noesis/cli/commands/diagnostics.py`).

### Changed
- Insight metrics now live under `noesis.domain.faculties.insight`; the legacy `noesis.insight` module issues a deprecation warning.
- Configuration plumbing no longer relies on `_config`; `EnvTomlConfig` composes defaults → TOML → env overrides without side effects, and all modules resolve configuration through injected ports.
- README, CHANGELOG, pyproject metadata, and release checklist document the new configuration boundary and migration steps.

### Removed
- Deprecated `noesis.config` shim and the `_config` module.

### Tests
- Suites now reset through the `ConfigPort`, and new coverage exercises diagnostics flows plus port validation.

### Breaking Changes
- Removed legacy config APIs; adopters must migrate to `EnvTomlConfig` or supply a runtime context.

## v0.5.3 – 2025-10-30
### Added
- Runtime context (`noesis.runtime.create_runtime_context`) with an extensible, versioned port registry.
- Memory and insight port protocols (`noesis.interfaces.memory`, `noesis.interfaces.insight`) ship as `1.0-rc1` contracts with capability checks.
  - Note: these stabilize to `1.0` next minor; `rc1` adapters remain supported for one transition release.
- CLI `--port` flag, `[ports]` config stanza, and plugin discovery (`noesis.plugins`) power deterministic adapter loading.
- Episode summaries include the active port manifest under `ports` for auditability.
- Tests covering env/TOML precedence, context-aware learning flows, and CLI JSON output.

### Changed
- Runtime components resolve configuration through injected ports, removing lingering `_config` dependencies from the execution path.
- README documents port registration, context usage, and the `--port` CLI flow.

## v0.4.3 – 2025-10-30
### Added
- **Incident-triage demo dashboards** now include seeded artifacts, timeline filters, learn badges, approval simulation, download buttons, and pure public-API reads.
- **New tests** covering config-shim warnings, run-directory creation, and approval-path flow.
- **Import-linter contracts** reinforcing the config-shim boundary and ensuring examples import only the public surface.

### Changed
- **Configuration internals** moved to `noesis._config`; the legacy `noesis.config` shim now emits a `FutureWarning` and will be removed in **v0.6**.
- **Environment variable** `NOESIS_DIRECTION_MIN_CONFIDENCE` supersedes the older alias `NOESIS_DIR_MIN_CONFIDENCE` (still accepted with a warning for now).
- **Public API** now exposes `noesis.get()` (wrapper for `_config.get`) and `noesis.paths()` for quick access to artifact locations.

### Docs
- **README** clarifies that `noesis.config` is legacy and scheduled for removal in v0.6, with updated examples using `noesis.set(...)`.

---

## v0.4.1 – 2025-10-30
### Added
- Learn events with configurable record/apply modes, persisted per-episode logs, and policy snapshots.
- Insight metrics now expose `learn_proposals` and `learn_applied`; CLI demo prints learn payloads for quick inspection.

### Changed
- Direction interventions can now rewrite string inputs (used by the SQL-guard demo) so patches increment applied counts.
- Veto rates omitted when none occur, reducing noisy zeroes in dashboards.
- Insight summaries normalize metrics (`act_count`, `reflect_count`, latencies, and pruned experimental buckets) and drop empty sections for cleaner artifacts.

---

## v0.4.0 – 2025-10-30
### Added
- Verb-based event timeline (`observe → learn`) with minimal payload contracts and automatic stubs when adapters stay silent.
- Insight metrics now include `steps`, `plan_count`, `reflect_count`, and structured latencies, while retaining legacy fields for compatibility.
- Documentation stubs for the cognitive loop, event-verb reference, and a cookbook recipe to inspect episodes.

### Changed
- Core emits `reflect` before `terminate`, keeping terminate semantics stable while enriching the loop with success metadata.
- Summary schema bumped to **1.1.0**; version set to **0.4.0**. Older episodes remain compatible.

---

## v0.3.1 – 2025-10-29
### Added
- Dedicated `insight` phase events recognized by the schema validator.
- Summaries record wall-clock `duration_sec` based on start/terminate timestamps.
- Direction demo prints active configuration so overrides are visible in CLI runs.

### Changed
- Public API frozen to `{run, solve, list_runs, summary, events, set, Intuition, DirectedIntuition, NoesisVeto}`, with experimental adapters and metrics helpers noted in docs.
- Metric surfaces deduplicated; summaries keep `veto_rate` / `top_reasons` without the legacy `direction_*` aliases.
- Flags report `mode="off"` when intuition is disabled and omit empty policy tags.
- CLI rebuilt with shared `-j / -q` ergonomics, `version` command, experimental `new` scaffolder, and richer human output for `list`, `show`, and `events`.
- Global flags: `--compact`, `--verbose`, `--debug`. `noesis insight` shortcut added. Stress tests gated behind `--stress` / `--debug`.
- Metrics trimmed to trusted fields (`success`, direction stats, latencies); placeholders moved to `metrics.experimental`.
- Insight latency metrics rounded up to nearest ms to avoid `0` when direction follows immediately after `start`.

### Tests
- Regression coverage for insight-phase validation, duration computation, and the new metrics/flag conventions.

---

## v0.2.0 – 2025-10-28
### Added
- CLI (`noesis`) with `run`, `solve`, `list`, `show`, `events`, `demo`.
- Config-file support (`noesis.toml` / `.noesis.toml`).
- `ns.set(direction_min_confidence=...)` knob (and CLI `--dir-min`).
- Direction flags & diffs exposed in summaries/events.

### Tests
- Config-loader tests and direction-reason-code coverage (7 passing).

### Docs
- README quickstart (CLI-first) and `docs/direction` overview/how-to.

---

## v0.1.0 – Project Initialized
- Established folder and module scaffolding.
- Added LangGraph adapter stub.
- Added documentation, schemas, and governance templates.
- Defined Apache-2.0 license and contribution guide.
