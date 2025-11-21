# ADR-004 — Runtime Determinism & Replayability

- **Status:** Accepted
- **Date:** 2025-11-20
- **Owner:** Sara Loera (saraeloop)
- **Reviewers:** Core Engineering, Runtime/Infra, Observability
- **Related roadmap items:** ADR-001, ADR-002, ADR-003, ADR-006 “ADR-004 replay tooling” (Phase 0)

---

## 1. Context

ADR-001/002/003 tightened runtime sessions, artifact integrity, and schema governance, but replay remained “best effort”: timestamps, event IDs, and ULID entropy were pulled from wall clock / uuid4 / os.urandom. Golden fixtures and auditing tools could not diff runs structurally; `events.jsonl` drifted even under identical tasks/seeds. ADR-004 (replay tooling) requires byte-stable artifacts and deterministic cognitive traces to diagnose regressions and reproduce customer incidents.

## 2. Decision

Adopt a deterministic execution path gated by an explicit `DeterminismConfig` and make tests assert structural equality of artifacts.

1. **Deterministic primitives.**
   - `DeterministicClock` (fixed-step `now()`, `start()`, `stop()`, resettable tick counter) feeds metrics/timestamps.
   - `DeterministicRNG` reseeds stdlib/numpy, exposes `bytes()`, `uuid_namespace()`, `event_id_factory()`, and `patch_os_urandom()` for ULID fixtures.
2. **Session wiring.**
   - `SessionBuilder.with_determinism(clock, rng, episode_timestamp_ms)` stores a `DeterminismConfig`; `NoesisSession.run/solve` forward it into `core.run_using`.
3. **Core + ULID determinism.**
   - `EpisodeIds.mint/new_episode_ulid` accept `timestamp_ms` + caller entropy; when determinism is on, ULID state is reset and entropy comes from `DeterministicRNG.bytes()`.
   - Pre-plan event UUID factory derived from the episode’s directive namespace; reused for all pre-run events.
4. **Deterministic event emission.**
   - Runtime event helpers (`start/observe/interpret/plan/act/reflect/direction/governance/terminate`) accept `now_fn` + `id_factory`, defaulting to legacy behavior.
   - Core passes deterministic `now_fn`/`id_factory` through intuition, plan/observe/start/terminate, and minimal-mode flow.
   - `RuntimeEventBus` gains injectable `now` + `event_id_factory`; `EpisodeInstrumentation` reuses them so cognitive events carry deterministic IDs/timestamps.
   - Minimal-mode snapshots store `state_path` relative to the run dir to avoid absolute-path drift in `events.jsonl`.
5. **Replay-safe tests.**
   - `test_deterministic_session_runs_are_byte_identical` builds two sessions with shared `DeterminismConfig`, then asserts:
     - `summary.json` byte-equal (canonical dump).
     - `state.json`/`manifest.json` structurally equal after stripping observational timestamps/hashes.
     - `events.jsonl` structurally equal after stripping IDs/timestamps/snapshots recursively.
     - No extra files appear across runs.

### Non-goals
- Determinism is opt-in; default runtime behavior (wall-clock, uuid4, os.urandom) remains unchanged.
- External adapters with nondeterministic side effects are out of scope; ADR-004 covers core/minimal paths and infrastructure-owned events.

## 3. Consequences

- Deterministic mode yields reproducible artifacts and stable cognitive traces for ADR-004 replay tooling and golden fixtures.
- Legacy runs stay nondeterministic unless `DeterminismConfig` is provided.
- Event writers must honor optional `now_fn`/`id_factory`; new adapters should plumb them when determinism is requested.
- Canonical JSON dumps (sorted keys, trailing newline) + relative snapshot paths keep summaries/manifests byte-stable.

## 4. Alternatives considered

1. **Record/replay wall-clock deltas only.** Rejected: still leaves uuid4/ulid entropy nondeterministic and fails structural comparisons.
2. **Hash-based deduplication of events.jsonl lines.** Rejected: loses ordering/metrics and hides genuine drift; not sufficient for replay tooling.
3. **Deterministic mode via global monkeypatches.** Rejected: harder to scope; explicit `DeterminismConfig` keeps determinism opt-in and testable.

## 5. Acceptance criteria

- Providing `DeterminismConfig` results in identical `summary.json` bytes across repeated runs of the same task/seed.
- `events.jsonl` sequences are structurally identical (after stripping observational fields) across deterministic reruns.
- ULIDs and event IDs are derived from deterministic clock/entropy under deterministic mode; no leakage from prior runs (ULID state reset).
- `RuntimeEventBus`/`EpisodeInstrumentation` honor injected `now`/`event_id_factory`; governance/direction metrics remain consistent in tests.
- Tests in `tests/runtime/test_determinism.py` pass and guard the structural invariants above.

## 6. Migration plan

1. Land deterministic primitives in `noesis.runtime.determinism`.
2. Extend session/core plumbing to accept `DeterminismConfig`; reset ULID state when passed.
3. Add `now_fn`/`id_factory` to runtime event helpers and thread through core + `RuntimeEventBus` + minimal runner.
4. Normalize snapshot paths (relative) and ensure canonical JSON writes remain in place.
5. Update tests to assert structural determinism and cover deterministic clock/RNG helpers.
6. Add ADR-004 to internal docs and reference in future replay tooling (ADR-006) work.

## 7. Open questions / risks

- Do we need deterministic coverage for adapters with external side effects (network/IO), or is deterministic mode confined to minimal/core paths?
- How to expose determinism toggles in CLI/SDK without confusing users who expect realtime behavior?
- Should we store deterministic seeds/entropy alongside artifacts to aid offline replay tooling?

## 8. References

- `noesis/runtime/determinism.py`, `noesis/runtime/session/models.py`, `noesis/core.py`
- `tests/runtime/test_determinism.py`
- ADR-001 (runtime session), ADR-002 (artifact integrity), ADR-003 (schema governance)
