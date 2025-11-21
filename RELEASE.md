# Noēsis Release Readiness Checklist v1.1+

> **Note:** This checklist is aspirational for post–v1.0.0 releases.  
> For the first GA release, use `internal_docs/release/v1.0.0-release-checklist.md`.  
> v1.1+ is where we turn on the “big guns”: SBOMs, OTLP/telemetry hardening, policy audits, and the fancy TUI/UX around the CLI.

This checklist turns the stability guidelines into a repeatable public release ritual.  
Start from a clean branch, confirm the freeze window is active, and target a tagged semantic version.

**Legend**
- `[Manual]` requires a human to execute or confirm.
- `[CI]` runs automatically; ensure the pipeline signal is green.

## 0. Freeze window administration

- [Manual] Announce the **release** freeze window (≥ 3 weeks before GA for major/minor releases) and pin it in `RELEASE.md` + `#announcements`.
- [Manual] Apply GitHub labels `freeze-candidate` / `post-1.0` and move deferred work into the 1.1 board.
- [CI] Confirm the schema-diff guard (post-freeze blocker) is enabled and green for the current default branch.

## 1. Freeze public interfaces

- [Manual] Update `CHANGELOG.md` with highlights and migration notes; link the version matrix excerpt.
- [Manual] Bump `noesis.__version__`, `SUMMARY_SCHEMA_VERSION`, and any state schema constants.
- [Manual] Verify no deprecated shims are importable without `NOESIS_LEGACY_SHIMS=1`; remove stragglers.
- [Manual] Confirm exported modules match the documented API surface (CLI, adapters, helpers).
- [Manual] Run `uv run scripts/validate_exports.py --strict` to diff `__all__` vs. docs; commit results.
- [Manual] Lock schema and policy version tuples in `noesis/trace/schema/__init__.py` and `noesis/domain/faculties/versioning.py`.
- [CI] Ensure the release freeze guard rejects backwards-incompatible schema bumps once the freeze starts.

## 2. Validate runtime durability

- [Manual] Run `uv run python -m pytest` (or your standard runner) and confirm all suites pass.
- [Manual] Execute two representative episodes (minimal + external adapter) and archive `events.jsonl` + summaries.
- [Manual] Run `noesis artifacts verify <episode_dir>` for each archived run and confirm manifest integrity.
- [Manual] Run `noesis diagnostics --replay tests/fixtures/demo_run` and confirm metrics match the golden tolerance.  
  _Planned for v1.1+; implement the replay CLI before enforcing this step._
- [Manual] Terminate a governed run mid-flight (SIGINT) and verify `summary.status="aborted"` with valid `phase_ms`.
- [Manual] Run a governed episode (`PlannerMode=governed`) and confirm veto propagation through governance → direction → insight logs.

## 3. Configuration and CLI checks

- [Manual] Execute `noesis diagnostics` and clear any warnings before proceeding.
- [Manual] Flip `PlannerMode` via `NOESIS_PLANNER` and `ns.set(planner_mode=...)`; ensure direction/governance phases appear or disappear appropriately.
- [Manual] Validate CLI ergonomics on bash and zsh: quoted `--port` specs, `noesis view`, `noesis migrate`, `python -m noesis`.
- [Manual] Install extras: `pip install .[migrate]`, `pip install .[ui]` and confirm clean imports plus dependency lists.
- [Manual] Regenerate and spot-check shell completions (`noesis completion bash/zsh`).
- [CI] Confirm the `cli-smoke` job runs every CLI command with `--help` and is green.

## 4. Learning and policy safeguards

- [Manual] Inspect `learn_home` for applied policy updates; ensure every proposal has a reversible handle with a signed diff.
- [Manual] Audit direction policies for confidence thresholds, veto behavior, and experimental toggles.
- [Manual] Confirm `policy_aliases` are up to date, documented, and covered by tests.
- [Manual] Re-run `pytest tests/learning/test_policy_proposals.py` after any governance change.
- [Manual] Execute `noesis learn audit` to surface orphaned or un-reverted proposals.
- [Manual] Compare `policy_score` trends across recent benchmark runs (target ≥ 10 % improvement or ≤ 5 % regression).

## 5. Operational readiness

- [Manual] Build signed artifacts: `uv build --sign --metadata release.yaml`; archive hashes.  
  _Signing/metadata flow can land in v1.1+; for earlier releases, a plain `uv build` is acceptable._
- [Manual] Generate SBOM and attestations (`scripts/generate_sbom.sh` → `dist/noesis-vX.Y.Z-sbom.json`).  
  _SBOM script may be introduced in v1.1+; treat this as a future requirement until the script exists._
- [Manual] Create a clean virtual environment, install `dist/noesis-*.whl` with `pip install --no-deps`, and confirm import fidelity.
- [Manual] Smoke-test CLI (`noesis run "Hello"`, `noesis view last`) inside the clean environment.
- [Manual] Set `NOESIS_OTLP_URL` to a mock endpoint and ensure telemetry gracefully falls back or succeeds.  
  _Telemetry/OTLP integration is a v1.1+ goal; skip or stub until available._
- [Manual] Update deployment playbooks, dashboards, and monitoring integrations with the new version.

## 6. Finalise release artefacts

- [Manual] Tag the release: `git tag -s vX.Y.Z -m "Noēsis vX.Y.Z"` and push with signatures.
- [Manual] Draft the GitHub release; attach wheels, SBOM, hashes, and the changelog excerpt.
- [Manual] Paste the runtime × schema × policy version matrix table into the release notes.
- [CI] Confirm the docs link checker (`pnpm nextra check-links` or equivalent) passes on the release commit.
- [Manual] Announce support timelines and upgrade guidance (Docs site, X, internal Slack) with a `noesis migrate` cheat sheet.

## Optional automation

- [Manual] Run `uv run scripts/pre_release.py --check-all` if available; this helper aggregates lint, tests, docs, link checks, and version assertions into a single ✅ / ❌ summary.

I'm keeping this checklist under version control and revise it whenever the platform gains new capabilities or operational requirements. That way every public release follows the same transparent playbook.