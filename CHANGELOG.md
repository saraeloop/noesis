# Changelog

## Unreleased
### Breaking
- Intuition protocol and helpers now live in `noesis.intuition`; update imports from `noesis.intuition.base` or `noesis.intuition.mode` to the consolidated module.
- Direction helpers moved to `noesis.direction` (formerly `noesis.intuition.DirectedIntuition`); adjust custom policy imports accordingly.
- Insight metrics are exposed from `noesis.insight.compute_metrics`, replacing the previous `noesis.eval.metrics.compute_metrics`.

### Added
- New `noesis.insight` module for lightweight run analytics.
- Trace helpers split into `noesis.trace.events` and `noesis.trace.summary` for clearer extension points.


## v0.2.0 - 2025-10-28
### Added
- CLI (`noesis`) with `run`, `solve`, `list`, `show`, `events`, `demo`.
- Config file support (`noesis.toml` / `.noesis.toml`).
- `ns.set(direction_min_confidence=...)` knob (and CLI `--dir-min`).
- Direction flags & diffs exposed in summaries/events.

### Tests
- Config loader tests, direction reason-code coverage (7 passing).

### Docs
- README quickstart (CLI-first) + docs/direction (overview/how-to).


## v0.1.0 — Project Initialized
- Established folder and module scaffolding.
- Added LangGraph adapter stub.
- Added documentation, schemas, and governance templates.
- Defined Apache-2.0 license and contribution guide.

