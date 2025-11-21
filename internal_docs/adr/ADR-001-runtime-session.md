# ADR-001 — Runtime Ownership & `NoesisSession`

- **Status:** Accepted  
- **Date:** 2024-11-15  
- **Owner:** Sara Loera (saraeloop)  
- **Reviewers:** Core Engineering  
- **Related roadmap items:** Phase 0 “Road to v1.0.0”, ADR-002, ADR-003  

---

## 1. Context

The legacy public API (`noesis.run/solve/set`) relied on a process-wide `RuntimeContext` singleton. Configuration changes (`ns.set`), port registration, and tests all mutated shared global state. That made deterministic tests brittle, blocked per-run isolation (e.g., concurrent benchmarks or multi-tenant services), and made it hard to reason about threading/reentrancy or planner/governor guarantees.

Phase 0 requires an explicit owner of runtime state. We need a typed session object that collects config, ports, determinism settings, and contextual defaults while keeping the `ns.*` facade backward-compatible via a default session provider.

---

## 2. Decision

Introduce a `NoesisSession` that aggregates runtime configuration, dependency injection, and execution helpers. All module-level helpers (`ns.run`, `ns.solve`, `ns.set`, CLI commands) route through a session instance. The singleton context is now an implementation detail of `DefaultSessionProvider`, not the public API.

### 2.1 Module structure

```
noesis/runtime/session/
├── __init__.py      # Public exports: NoesisSession, SessionConfig, SessionBuilder, RunnerProtocol, DefaultSessionProvider
├── models.py        # SessionConfig + SessionBuilder + DeterminismConfig dataclasses
├── provider.py      # DefaultSessionProvider with ContextVar-based scoped overrides
├── session.py       # NoesisSession: holds config/context, orchestrates .run/.solve/.configure
├── runner_port.py   # RunnerProtocol contract for BYO graph/adapter execution
└── threading.py     # SessionLock guard for single in-flight run
```

- **Domain entities (session models):** `SessionConfig(snapshot, default_tags, determinism)` (immutable), optional `DeterminismConfig(clock, rng, episode_timestamp_ms)`.
- **Use cases (session orchestration):** `NoesisSession.run/solve` compose core runners/planners and forward determinism and tags.
- **Interface adapters:** CLI and `ns.*` route through `DefaultSessionProvider.current()` instead of touching the legacy `RuntimeContext` singleton.
- **Infrastructure:** `DefaultSessionProvider` memoizes the process default session and allows scoped overrides via `ContextVar`; `SessionLock` enforces single-run execution per session.

### 2.2 Core code (snapshot)

```python
# noesis/runtime/session/models.py
@dataclass(slots=True, frozen=True)
class DeterminismConfig:
    clock: DeterministicClock
    rng: DeterministicRNG
    episode_timestamp_ms: Optional[int] = None

@dataclass(slots=True, frozen=True)
class SessionConfig:
    snapshot: ConfigSnapshot
    default_tags: Mapping[str, Any] = field(default_factory=dict)
    determinism: Optional[DeterminismConfig] = None

class SessionBuilder:
    def with_port(self, name: str, provider: Any, *, api: str) -> "SessionBuilder": ...
    def with_default_tags(self, **tags: Any) -> "SessionBuilder": ...
    def with_determinism(self, *, clock: DeterministicClock, rng: DeterministicRNG, episode_timestamp_ms: Optional[int] = None) -> "SessionBuilder": ...
    def build(self) -> NoesisSession: ...
```

```python
# noesis/runtime/session/session.py
class NoesisSession:
    def configure(self, **overrides: object) -> SessionConfig: ...
    def run(..., runner: RunnerProtocol | None = None, tags: MutableMapping[str, Any] | None = None,
            intuition: bool | Intuition | None = True, seed: int = 0) -> str: ...
    def solve(..., using: Any, tags: MutableMapping[str, Any] | None = None, seed: int = 0) -> str: ...
    def with_ports(self, **ports: tuple[Any, str]) -> "NoesisSession": ...
```

```python
# noesis/runtime/session/provider.py
class DefaultSessionProvider:
    def current(self) -> NoesisSession: ...
    @contextmanager
    def use(self, session: NoesisSession) -> Iterator[None]: ...
```

### 2.3 Test examples (present today)

- `tests/runtime/test_determinism.py` builds two sessions via `SessionBuilder.with_determinism(...)` and asserts deterministic artifacts across runs; `SessionLock` guards single in-flight runs.
- Session isolation is achieved by constructing a fresh builder per scenario (e.g., `_FakeConfigPort` in determinism tests); module-level `ns.*` helpers delegate through `DefaultSessionProvider`.

### 2.4 Integration points

1. `noesis/__init__.py` re-exports `NoesisSession`, `SessionBuilder`, `DefaultSessionProvider`, and `create_session`; `ns.run/solve/set` delegate to the provider-backed session.
2. `noesis/core.py` accepts injected context/determinism and is called by `NoesisSession.run/solve`.
3. CLI commands build/consume a session via the provider; scoped overrides are supported via `DefaultSessionProvider.use(...)`.
4. Legacy read-only helpers (`context`, `events`, `summary`) continue to rely on the active session’s runtime context.

### 2.5 Clean Architecture mapping

- **Entities:** SessionConfig/DeterminismConfig remain pure dataclasses; EpisodeRequest/PlanStep stay in their domains.
- **Use cases:** NoesisSession.run/solve orchestrate `EpisodeRunner`, planners, and governors with injected dependencies.
- **Interface adapters:** CLI and `ns.*` wrap the session—no domain leakage.
- **Infrastructure:** DefaultSessionProvider, config/env loaders, filesystem-backed runs directory.

---

## 3. Consequences

- **Determinism:** Tests and services instantiate sessions instead of mutating globals; `DeterminismConfig` is plumbed through builder → session → core to support replay safety.
- **Extensibility:** Bring-your-own Runner implementations conform to `RunnerProtocol`; ports are injected rather than looked up globally.
- **Ergonomics:** Existing code continues to call `ns.run/solve/set`, but they delegate to `DefaultSessionProvider`. Scoped overrides allow per-CLI-invocation or per-test sessions without contaminating process state.
- **Threading guarantees:** `SessionLock` enforces single active run per session; `DefaultSessionProvider` uses `ContextVar` for scoped overrides and memoizes the process default.

---

## 4. Alternatives considered

1. **Keep the global `RuntimeContext` singleton.** Rejected: fails determinism and isolation goals.
2. **Expose bare `RuntimeContext` as the public session.** Rejected: context lacks orchestration helpers, determinism plumbing, and lifecycle hooks (manifest writing, governor wiring).
3. **Rely on dependency injection at every call site (no session).** Rejected: burdens consumers and makes CLI/`ns.*` unusable without boilerplate.

---

## 5. Acceptance criteria

- ADR-001 marked Accepted with reviewer sign-off.
- `NoesisSession` + `SessionBuilder` + `DefaultSessionProvider` are the public entrypoints; `ns.*` and CLI delegate through them.
- Determinism hooks are available via `SessionBuilder.with_determinism(...)` and honored by core runners.
- Tests demonstrating deterministic runs and session isolation are present and passing.
- Documentation (README/ROADMAP/DeepWiki) references `NoesisSession` as the owner of runtime state and shows at least one session-based example.

---

## 6. Migration plan

1. Introduce `NoesisSession`/`SessionBuilder`/`DefaultSessionProvider` alongside legacy globals. ✔
2. Update `ns.*` wrappers + CLI to use `DefaultSessionProvider` instead of directly touching `RuntimeContext`. ✔
3. Ensure core runtime modules accept injected context/determinism via session calls (public entrypoints already do). ✔
4. Keep any legacy helpers behind explicit “legacy” flags/envs; avoid new surface area on the singleton context. ✔
5. Update docs/examples to prefer `NoesisSession` / `SessionBuilder` for new code. (In progress with v1.0.0 docs.)

---

## 7. Open questions / risks

- Do we need `ContextVar`-based session overrides for async frameworks and background tasks?
- How do we scope per-session caches (e.g., adapter reuse) without leaking memory across long-lived processes?
- Should `NoesisSession` surface diagnostics/inspection helpers (e.g., `session.summary.read(eid)`) or keep read APIs separate?

---

## 8. References

- ROADMAP Phase 0 trust-spine requirements
- `noesis/runtime/session/*` implementation and tests
- `noesis/__init__.py` `ns.*` wrappers
- `noesis/core.py` orchestration pipeline
