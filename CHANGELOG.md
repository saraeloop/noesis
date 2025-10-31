# Changelog

## Unreleased

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