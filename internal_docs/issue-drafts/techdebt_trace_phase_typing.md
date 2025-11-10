# Tech Debt: Enforce strict phase typing in `noesis/trace/events.py`

## Summary
Observability can ingest malformed phase names because `_validate_event_schema` only warns when the phase is outside the canonical set. Logging hook TODOs are still outstanding.

## Implementation Plan
- Core mechanism: introduce an enum (e.g., `Phase` or `CognitivePhase`) that enumerates Observe, Interpret, Plan, Act, Reflect, Learn, plus extension slots.
- Required schemas: update event schema definitions and validation logic to require enum membership unless flagged as experimental.
- Evaluation metric: CI schema tests and runtime diagnostics reject invalid phases; logging hook emits warnings with context.
- Training/eval datasets: regression event fixtures augmented with invalid-phase cases to ensure rejection.
- Required checkpoints/services: none.
- Safety considerations: allow feature flags for custom phases to prevent breaking downstream experiments.

## Expected Outcomes
- Telemetry integrity: downstream analytics can rely on canonical phase names.
- Faster debugging: logging integration surfaces schema violations immediately.

## Baselines & Metrics
- Baseline: current permissive validation (allows typos silently).
- Target metric: 100% of events in test fixtures pass enum validation; invalid events trigger actionable errors.
- Evaluation protocol: extend `tests/trace/test_events_validation.py` (add if missing) with positive/negative cases.

## Artifacts
- Updated schema fingerprint and docs.
- Unit tests demonstrating enforcement.
- Sample event payloads (valid + invalid).

## Related Work
- Aligns with roadmap items for schema guards and observability.

## Existing Assets
- TODO references in `noesis/trace/events.py` at lines ~90 and ~167.

## Notes
- Consider pairing with a docs update on adding experimental phases via feature flags.
