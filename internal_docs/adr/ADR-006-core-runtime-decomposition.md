# ADR-006 — Core Runtime Decomposition & Ports for Episode Orchestration

**Status:** Accepted
**Date:** 2025-12-09  
**Owner:** Noēsis maintainer (@saraeloop)  
**Since:** v1.0.0 (post-GA refactor)

⸻

## 1. Context

By v1.0.0, Noēsis has a stable substrate:

- **ADR-001 — Runtime ownership & `NoesisSession`.**  
  Session-first runtime model, `NoesisSession` / `ns.run/solve`, deterministic entrypoints.
- **ADR-002 — Artifact immutability & manifest.**  
  `events.jsonl`, `state.json`, `summary.json`, `manifest.json` with atomic writes + HMAC.
- **ADR-003 — Schema governance & KPIs.**  
  Schema versions, field-level stability flags, semver rules, and KPI definitions.
- **ADR-004 — Determinism substrate.**  
  `DeterminismConfig`, deterministic clocks/IDs, replay diagnostics and golden runs.
- **ADR-005 — Prompt provenance v1.1 (experimental).**  
  Optional `prompts.jsonl` with schema-governed prompt records and privacy modes.

These pieces are stable and tested. However, the core runtime orchestration has accumulated too many responsibilities in a small number of modules:

- **`noesis/core.py`:**
  - Public entrypoints: `run`, `solve`, `run_using`, `run_graph`, `set`.
  - Episode orchestration: minting episode IDs, setting up `EpisodeContext`, constructing `RuntimeStateRepository`, `EpisodeRunner`, and the event bus.
  - Determinism wiring: `DeterminismConfig`, deterministic clocks/IDs, minimal vs META / adapter execution.
  - Minimal vs adapter paths: `core.minimal` planner/actuator, adapter selection and invocation.
  - Artifact finalization: `summary.json`, `manifest.json`, episode index.
- **`noesis/usecases/episode_runner.py`:**
  - Coordinates planners, actuators, governance (`PreActGovernor`), state repository, and event emission.
  - Uses concrete types such as `RuntimeStateRepository` and `PromptRecorder` directly.

Architecture review (Clean Architecture lens) highlights some concrete problems:

1. **Application/use-case layer depends on infra concretions.**  
   `EpisodeDependencies` and `EpisodeRunner` take a concrete `RuntimeStateRepository` and reach into runtime helpers (`read_events`, `PromptRecorder`) instead of abstract ports. This makes the use case layer hard to test in isolation and tightly couples it to the filesystem and prompt recorder implementation.

2. **Core orchestration mixes policy, orchestration, and infrastructure wiring.**  
   `_run_impl(...)` in `noesis/core.py`:
   - Loads config, sets up determinism, constructs state repositories and event buses,
   - Builds planners, actuators, governors,
   - Branches between minimal vs adapter execution,
   - Finalizes artifacts and indexes.  
   This violates single responsibility and makes the core difficult to extend or reason about.

3. **Global runtime context singleton still exists.**  
   `get_context()` auto-creates a global context and is still used as a default. This undermines ADR-001’s “session owns runtime” principle and is risky under concurrency.

There is also an existing issue describing the need for this refactor:

> **[Feature] refactor(core): split episode orchestration + adapter integration into smaller units (post-1.0.0) #39**

This ADR formalizes what we want the architecture to look like and how we’ll refactor toward it.

⸻

## 2. Decision

We will:

1. **Introduce explicit ports for episode orchestration**  
   (Clean Architecture: use-case layer depends only on ports, never on infra concretions):

   - Define interfaces/protocols in the application/use-case layer for:
     - `StateRepositoryPort` (read/write state, list episodes),
     - `EventSinkPort` / `EventBusPort` (append events, flush),
     - `PromptRecorderPort` (record prompt provenance where enabled),
     - `ClockPort` / `IdFactoryPort` (if needed explicitly).
   - Make `EpisodeRunner` and `EpisodeDependencies` depend on these ports, not on `RuntimeStateRepository`, `PromptRecorder`, or filesystem helpers.
   - Expose the public import path as `noesis.ports` (aliasing `noesis.usecases.ports`) and forbid public examples/docs from importing `noesis.usecases.*`.

2. **Decompose `noesis.core` into smaller, mode-specific orchestrators**  
   without changing the public API:

   - Keep public entrypoints (`run`, `solve`, `run_using`, `run_graph`) intact.
   - Split the internal orchestration into:
     - `_run_minimal_episode(...)` — for `core.minimal` runs,
     - `_run_adapter_episode(...)` — for adapter-backed runs.
   - Extract shared helpers for:
     - Episode initialization (ID, context, ports construction),
     - Summary finalization,
     - Manifest + index finalization,
     - Determinism wiring (so both paths reuse the same logic).

3. **Constrain global runtime context to legacy shims only**

   - Enforce session-first usage:
     - New and primary paths require an explicit `NoesisSession` / `RuntimeContext`.
   - Keep the global `get_context()` only for:
     - Legacy `noesis.run(...)` / `noesis.solve(...)` convenience,
     - CLI entrypoints that do not yet pass a session object.
   - Internally, all new orchestration calls will receive a context/session explicitly; they will not read the global singleton directly.

4. **Preserve all external behavior and artifacts for v1.0.x**

   - No changes to:
     - Artifact schemas or schema versions,
     - Replay gates or determinism semantics,
     - CLI flags or core API signatures.
   - The refactor must be validated by:
     - Existing test suite (unit + integration),
     - Determinism tests (including veto scenarios),
     - Replay diagnostics (`diagnostics replay`) on golden runs.

This ADR is structural: it does not introduce new features. It reduces coupling, clarifies boundaries, and makes Noēsis safer to extend (for adapters, telemetry, or multi-agent runtimes) without breaking the v1.0.0 contracts.

⸻

## 3. Rationale

### 3.1 Clean Architecture & testability

Today, `EpisodeRunner` cannot be used in a pure unit test without:

- A real `RuntimeStateRepository`,
- Filesystem access for `events.jsonl` / `state.json`,
- A concrete `PromptRecorder`.

This violates the Clean Architecture rule: use cases depend on abstractions, not on infrastructure.

By introducing ports:

- We can test the episode orchestration with in-memory or fake implementations.
- Integrations (LangGraph, CrewAI, Gradient, Bedrock AgentCore, etc.) can supply their own state/event sinks if they want.

### 3.2 Runtime extensibility

Noēsis is not a LangGraph plugin or a CrewAI fork; it’s a cognitive runtime that must:

- Run in CLIs,
- Export traces into different telemetry systems (LangSmith, OpenTelemetry, homegrown),
- Work with multiple agent frameworks.

If core orchestration is a big ball of concrete classes, each new integration becomes invasive. With clear ports:

- You can create alternate infra implementations (e.g., `OpenTelemetryEventSink`, `LangSmithStateRepository`) in outer layers,
- Without touching the episode logic.

### 3.3 Containing global state

ADR-001 says the session owns the runtime. The remaining global context:

- Makes behavior under concurrency harder to reason about,
- Creates surprising interactions when multiple callers use `noesis.run()` in the same process.

Constraining the singleton to legacy/shim paths moves Noēsis closer to the intended model:

> “A session is the unit of ownership; all state is passed explicitly.”

⸻

## 4. Detailed Design

### 4.1 Ports for episode orchestration

In an application/use-case module (public surface `noesis/ports.py`, implemented in
`noesis/usecases/ports.py`):

```python
from typing import Protocol, Any, Mapping, Iterable

class StateRepositoryPort(Protocol):
    context: Any
    def init(self, request: Any | None = None) -> NoesisState: ...
    def persist(self, state: NoesisState) -> None: ...

class EventSinkPort(Protocol):
    def emit(self, event: CognitiveEvent, agent_id: str = "system") -> None: ...

class PromptRecorderPort(Protocol):
    def is_enabled(self) -> bool: ...
    def record(
        ...,
        rendered: str,
        tags: Mapping[str, str] | None = None,
        ...
    ) -> None: ...

class ClockPort(Protocol):
    def start(self, label: Any) -> Any: ...
    def stop(self, token: Any) -> Any: ...
    def now(self) -> datetime: ...

class EventIdFactoryPort(Protocol):
    def __call__(self) -> UUID: ...
```

These ports are **domain-shaped**:

- `StateRepositoryPort` operates on domain state (e.g., `NoesisState.to_dict()` payloads), not arbitrary mappings.
- `EventSinkPort`/`EventBusPort` operate on `CognitiveEvent` payloads (or strongly typed equivalents) and support `flush`.
- Determinism requires injecting `ClockPort` + `IdFactoryPort`; default impls wrap `DeterministicClock`/`RuntimeClock` and deterministic UUID/ULID factories.

Concrete bindings (outer layer):

- `RuntimeStateRepository` → `StateRepositoryPort`
- `RuntimeEventBus` + `CognitiveEventEmitter` → `EventSinkPort`/`EventBusPort`
- `PromptRecorder` → `PromptRecorderPort` (with no-op impl when disabled)
- `DeterministicClock` / `RuntimeClock` → `ClockPort`
- `determinism.rng.event_id_factory` / `uuid4` → `IdFactoryPort`

### 4.2 Core decomposition plan

- Keep public API (`run/solve/run_using/run_graph`) stable.
- Split orchestration internals:
  - `_run_minimal_episode(...)`
  - `_run_adapter_episode(...)`
- Extract factories (outer/runtime layer):
  - `make_episode_context(cfg, determinism, task, tags, using_label)`
  - `make_ports(context, determinism)` → returns state repo port, event bus port, prompt recorder port, clock/id factories.
  - `finalize_summary(...)`, `finalize_manifest_and_index(...)` reused by both paths.
- Keep adapter selection (`_select_adapter`) in the outer layer; use-case logic should receive an already-wrapped actuator/adapter port.

### 4.3 Prompt provenance handling

- `PromptRecorderPort` is injected; when provenance is disabled, bind a no-op impl.
- Deterministic mode uses injected `ClockPort`/`IdFactoryPort` for timestamps and IDs; hashing remains deterministic.
- Ports keep prompt schema compatibility; no schema/version changes in this refactor.

### 4.4 Acceptance criteria (must all hold)

- Behavior: artifacts (`events.jsonl`, `state.json`, `summary.json`, `manifest.json`, optional `prompts.jsonl`) and schema versions are unchanged.
- Determinism: existing replay tests stay green (byte-stable summaries/manifests; structural event equality).
- Import-linter: new contracts added to forbid use-case layer importing runtime/infra; CI enforced.
- Public surface: ports are exposed via `noesis.ports`; docs/examples/tests use the facade and do not import `noesis.usecases.*`.
- Tests: unit and integration suites pass; determinism + veto scenarios pass; schema guard unaffected.
- Public API: signatures and CLI flags unchanged.

### 4.5 Migration plan

1) ✅ Introduce ports module (`noesis/ports.py` → `noesis/usecases/ports.py`) and no-op prompt recorder.  
2) ✅ Add outer-layer factories to build concrete ports from `SessionConfig` + determinism (`_bootstrap_episode` + `_build_runner_ports`).  
3) ✅ Refactor `EpisodeRunner` to consume ports (no direct `RuntimeStateRepository`, `PromptRecorder`, `read_events`).  
4) ✅ Split `core` into `_run_minimal_episode` / `_run_adapter_episode` using shared helpers and deterministic-friendly runner ports.  
5) ✅ Gate `get_context()` to legacy shims/public convenience; internal orchestration is session/context-first.  
6) ✅ Strengthen import-linter/CI and backfill tests for new ports wiring (contracts now block `usecases` → {adapters, cli}).  
7) ✅ Consolidate runtime wiring under the ports-based path; no dual code paths remain for episode orchestration.

### 4.6 Current implementation status (2025-12-09)

- Ports package exported (`noesis/ports.py` aliasing `noesis/usecases/ports.py`) and enforced by import-linter.
- Public surface validated: docs/API reference list `noesis.ports`; public import smoke test covers the facade; docs/examples forbid `noesis.usecases.*`.
- `EpisodeRunner` now depends on ports for state/events/prompt/clock/history via structural adapters; behavior unchanged.
- `core.py` is decomposed into `_run_minimal_episode` / `_run_adapter_episode` with shared finalization and a common runner-port builder (clock/emitter/lineage) for both paths; public APIs intact.
- Import-linter: 6/6 contracts kept under Python 3.12 (new usecase boundaries included).
- `get_context()` is only used by public convenience entrypoints and the default session provider; internal orchestration uses explicit contexts/sessions.

### 4.7 Consequences / risks / timeline

- Pros: cleaner layering, easier testing with in-memory fakes, safer integrations (LangGraph/CrewAI/OTel) without touching core.
- Risks: temporary churn while both wiring styles coexist; must watch determinism regressions and schema drift.
- Global context (`get_context()`) is retained as a convenience entrypoint (and used by the default session provider); future tightening may require explicit sessions in all internal call sites.
- `EpisodeRunner` still constructs runtime defaults when instrumentation is omitted; future polish could inject ports-built instrumentation from core to keep usecases free of runtime concretes.
- Timeline: target post-GA (v1.0.x) in 2–3 PRs following the migration steps; keep release notes noting “internal refactor, no surface change.”

### 4.8 Follow-ups (post-ADR polish)

- Consider requiring explicit instrumentation injection for `EpisodeRunner` (or always building it in core) to remove remaining runtime defaults from the use-case layer.
- Consider hardening the public surface by warning or blocking direct `noesis.usecases.*` imports; keep `noesis.ports` as the documented extension point.
- Evaluate tightening the default session provider to avoid implicit `get_context()` creation in multi-tenant hosts.
