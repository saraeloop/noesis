# ADR-001 — Runtime Ownership & `NoesisSession`

- **Status:** Proposed
- **Date:** 2024-11-15
- **Owner:** Sara Loera (saraeloop)
- **Reviewers:** Core Engineering
- **Related roadmap items:** Phase 0 “Roas to v1.0.0”, ADR-002, ADR-003

---

## 1. Context

The current public API (`noesis.run/solve/set`) relies on a process-wide `RuntimeContext` singleton. Configuration changes (`ns.set`), port registration, and tests all mutate this shared global. This creates hidden state between runs, makes deterministic tests brittle, and blocks per-run isolation (e.g., concurrent benchmarks or multi-tenant services). It also makes it impossible to reason about threading/reentrancy and hampers our ability to enforce planner-mode guarantees because tests can’t assert which planner/governor were active per run.

Phase 0 requires us to “lock the trust spine” before landing more features. That spine starts with an explicit owner of runtime state. We need a typed session object that collects config, ports, and contextual defaults, while keeping the `ns.*` facade backward-compatible via a default session provider.

## 2. Decision

Introduce a `NoesisSession` that aggregates runtime configuration, dependency injection, and execution helpers. All existing module-level helpers (`ns.run`, `ns.solve`, `ns.set`, CLI commands) will route through a session instance. The singleton context becomes an implementation detail of the `DefaultSessionProvider`, not the API surface.

### 2.1 Module structure

```
noesis/runtime/session/
├── __init__.py            # Public exports: NoesisSession, SessionConfig, SessionBuilder
├── models.py              # Dataclasses / TypedDicts describing session inputs (runs_dir, planner mode, intuition policy refs)
├── provider.py            # DefaultSessionProvider managing process-level default session (for ns.* convenience)
├── session.py             # NoesisSession implementation: holds ports, orchestrates runs, exposes .run/.solve/.configure
├── runner_port.py         # RunnerProtocol defining the typed contract for Bring-Your-Own graph/adapter execution
└── threading.py           # Thread/concurrency guarantees (ReentrantReadWriteLock, context safeguards)
```

- **Domain entities (session models):** pure dataclasses describing session config, immutable once built.
- **Use cases (session orchestration):** `NoesisSession.run/solve` compose existing runners/planners but require explicit dependencies.
- **Interface adapters:** CLI and `ns.*` import from `noesis.runtime.session` instead of `runtime.config_provider`.
- **Infrastructure:** provider & threading helpers own the global default session and locking semantics.

### 2.2 Core code (key types & interfaces)

```python
# noesis/runtime/session/models.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, MutableMapping, Sequence
from noesis.interfaces.config import ConfigSnapshot, PlannerMode
from noesis.context import RuntimeContext

@dataclass(slots=True, frozen=True)
class SessionConfig:
    runs_dir: Path
    planner_mode: PlannerMode
    intuition_mode: str
    ports: Mapping[str, tuple[object, str]]
    tags: Mapping[str, object] = field(default_factory=dict)
    def bind(self) -> RuntimeContext: ...

# noesis/runtime/session/runner_port.py
from typing import Protocol
from noesis.usecases.episode_runner import EpisodeOutcome
from noesis.usecases.episode_runner import EpisodeRequest

class RunnerProtocol(Protocol):
    """Adapter contract for Bring-Your-Own graphs."""
    def run(self, request: EpisodeRequest, *, context: RuntimeContext) -> EpisodeOutcome: ...

# noesis/runtime/session/session.py
class NoesisSession:
    """Owns runtime config, ports, and execution helpers (single in-flight run per session unless stated otherwise)."""
    def __init__(self, *, config: SessionConfig, context: RuntimeContext | None = None) -> None: ...
    def configure(self, **overrides: object) -> SessionConfig: ...
    def run(self, task: str, *, seed: int = 0, intuition: bool | Intuition | None = True,
            tags: MutableMapping[str, object] | None = None, runner: RunnerProtocol | None = None) -> str: ...
    def solve(self, task: str, *, using: GraphSource, **kwargs: object) -> str: ...
    def with_ports(self, **ports: tuple[object, str]) -> "NoesisSession": ...
```

### 2.3 Test examples (pytest-style)

```python
import pytest
from noesis.runtime.session import NoesisSession, SessionConfig
from noesis.interfaces.config import PlannerMode

def test_session_isolation(tmp_path):
    cfg = SessionConfig(runs_dir=tmp_path, planner_mode=PlannerMode.MINIMAL, intuition_mode="advisory", ports={})
    session = NoesisSession(config=cfg)
    episode_a = session.run("Compute checksum", seed=7, intuition=False)
    episode_b = session.run("Compute checksum", seed=7, intuition=False)
    assert episode_a != episode_b
    assert (tmp_path / episode_a / "summary.json").exists()

def test_runner_protocol_injected(fake_runner, tmp_path):
    cfg = SessionConfig(runs_dir=tmp_path, planner_mode=PlannerMode.META, intuition_mode="advisory", ports={})
    session = NoesisSession(config=cfg)
    eid = session.run("task", runner=fake_runner)
    assert fake_runner.runs == [eid]
```

### 2.4 Integration points

1. `noesis/__init__.py` re-exports `NoesisSession` and `create_session`.
2. `noesis/core.py` becomes a thin orchestration module calling `DefaultSessionProvider.current().run(...)`.
3. CLI commands receive an explicit session (either built from CLI args or the default provider) and instantiate a fresh session per invocation (no reuse across CLI calls).
4. `events`, `summary`, `context` modules remain read-only helpers pointing at the active session’s runs directory.

### 2.5 Clean Architecture mapping

- **Entities:** `SessionConfig`, `EpisodeRequest`, `PlanStep` remain pure dataclasses, no IO.
- **Use cases:** `NoesisSession.run/solve` orchestrate `EpisodeRunner`, planners, governors.
- **Interface adapters:** CLI/`ns.*` functions wrap the session—no domain leakage.
- **Infrastructure:** `DefaultSessionProvider`, filesystem-based runs directory, config/env loaders.

## 3. Consequences

- Determinism: Tests instantiate their own session instead of mutating globals. Parallel pytest runs or notebook experiments no longer collide on `ns.set`.
- Extensibility: Bring-your-own Runner implementations register via the `RunnerProtocol`. Adapters declare capabilities explicitly.
- Ergonomics: Existing code continues to call `ns.run`, but it now delegates to `DefaultSessionProvider`. A `NoesisSession.for_test()` helper will construct sandboxed sessions for fixtures.
- Threading guarantees: `NoesisSession` documents whether it is re-entrant (default: single active run); provider enforces per-thread default session overrides via contextvars.
- Provider semantics: `DefaultSessionProvider` lazily instantiates the default session on first access using env/config defaults so initialization order stays deterministic.

## 4. Alternatives considered

1. **Keep the global `RuntimeContext` singleton.** Rejected: fails determinism/dx goals, no per-run encapsulation.
2. **Expose bare `RuntimeContext` as the public session.** Rejected: context currently only stores config/ports; it lacks orchestration helpers, acceptance of Runner protocols, or lifecycle hooks (manifest writing, governor wiring).
3. **Rely on dependency injection at every call site (no session).** Rejected: would burden every consumer with plumbing and make CLI/`ns.*` unusable without verbose boilerplate.

## 5. Acceptance criteria

- ADR merged with reviewer sign-off and migration note stub.
- `NoesisSession` module + provider scaffolding merged behind feature flag (no behavior change yet).
- Tests demonstrating isolated sessions and RunnerProtocol injection added.
- Documentation: README/ROADMAP references updated to mention `NoesisSession` as the owner of runtime state.

## 6. Migration plan (stub)

1. Introduce `NoesisSession` and adapter/provider scaffolding alongside current globals (no breaking change).
2. Update `ns.*` wrappers + CLI to use `DefaultSessionProvider`.
3. Migrate core runtime modules to require an injected session/context.
4. Remove direct usage of `runtime.config_provider` from public API; mark legacy helpers as deprecated.

## 7. Open questions / risks

- Do we need contextvars-based session overrides for async frameworks?
- How do we scope per-session caches (e.g., adapter reuse) without leaking memory?
- Should `NoesisSession` surface diagnostics/inspection methods (e.g., `session.summary.read(eid)`) or keep read APIs separate?

## 8. References

- ROADMAP Phase 0 trust-spine requirements.
- `noesis/runtime/config_provider.py` (current singleton).
- `noesis/core.py` orchestration pipeline.
