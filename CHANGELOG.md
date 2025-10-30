# Changelog

## Unreleased

## v0.4.0 - 2025-10-30
### Added
- Verb-based event timeline (`observe`→`learn`) with minimal payload contracts and automatic stubs when adapters stay silent.
- Insight metrics now include `steps` (act count), `plan_count`, `reflect_count`, and structured latencies while keeping legacy fields for compatibility.
- Documentation stubs for the cognitive loop, event verbs reference, and cookbook recipe to inspect episodes.

### Changed
- Core emits `reflect` before `terminate`, keeping terminate semantics stable while enriching the loop with success metadata.
- Summary schema bumped to 1.1.0 and version set to 0.4.0; no public API changes required and older episodes still render.

## v0.3.1 - 2025-10-29
### Added
- Insight events now emit as a dedicated phase and the schema validator recognises them.
- Summaries record wall-clock `duration_sec` based on start/terminate timestamps.
- Direction demo prints the active configuration so overrides are visible in CLI runs.

### Changed
- Public API frozen to `{run, solve, list_runs, summary, events, set, Intuition, DirectedIntuition, NoesisVeto}` with experimental adapters and metrics helpers noted in the docs.
- Metric surfaces deduplicated: summaries keep `veto_rate`/`top_reasons` without the legacy `direction_*` aliases.
- Flags now report `mode="off"` when intuition is disabled and omit empty policy tags.
- Rebuilt the CLI: shared `-j/-q` ergonomics, new `version` command, experimental `new` scaffolder stub, and richer human output across `list`, `show`, and `events`.
- CLI polish: global `--compact/--verbose/--debug`, `noesis insight` shortcut, compact demo output by default, and stress tests gated behind `--stress/--debug`.
- Metrics trimmed to trusted fields (`success`, direction stats, latencies); placeholders now live under `metrics.experimental` with nulls until defined.
- Insight latency metrics now ceil to the nearest millisecond, avoiding `0` when direction events follow immediately after `start`.

### Tests
- Added regression coverage for insight phase validation, duration computation, and the new metrics/flag conventions.


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
