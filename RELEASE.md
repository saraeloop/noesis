# Noēsis Release Readiness Checklist

This checklist turns the stability guidelines into concrete actions for every public release. 
It assumes you are working from a clean branch, targeting a tagged semantic version.

## 1. Freeze public interfaces

- [ ] Update `CHANGELOG.md` with highlights and breaking-change notes.
- [ ] Confirm `noesis.__version__`, `SUMMARY_SCHEMA_VERSION`, and state schema
      constants are bumped as needed.
- [ ] Review public APIs (`run`, `solve`, CLI commands, adapters) for backwards
      compatibility; document any deprecations with timelines.
- [ ] Regenerate or refresh reference docs that mirror the exported contracts.

## 2. Validate runtime durability

- [ ] Run `uv run python -m pytest` (or your chosen runner) and ensure all
      suites pass.
- [ ] Exercise the Observe → Interpret → Plan → Act → Reflect → Learn loop with
      representative adapters. Capture event logs for at least one minimal run
      and one external adapter run.
- [ ] Stress the runtime container resolution (CLI `--port`, `noesis.toml`,
      entry-point plugins) in isolated environments.
- [ ] Verify crash recovery by inspecting partially written runs (terminate a
      run mid-flight and confirm summaries remain well-formed).

## 3. Configuration and CLI checks

- [ ] Execute `noesis diagnostics` (added in this release) and confirm all
      checks report `ok`. Address any warnings before continuing.
- [ ] Validate CLI ergonomics on both bash and zsh, including quoted `--port`
      specs.
- [ ] Re-run `noesis validate-ports --json` to snapshot declared port APIs.

## 4. Learning and policy safeguards

- [ ] Inspect `learn_home` for applied policy updates; ensure every applied
      proposal has a reversible handle.
- [ ] Audit direction policies for confidence thresholds, veto behaviour, and
      experimental features toggles.
- [ ] Confirm `policy_aliases` are current and documented.

## 5. Operational readiness

- [ ] Produce a signed wheel / sdist via `uv build` (or equivalent) and capture
      hashes.
- [ ] Generate the SBOM / dependency audit and archive it alongside the build.
- [ ] Smoke test the built artifact inside a clean virtual environment.
- [ ] Update deployment playbooks, dashboards, and any external monitoring
      integrations.

## 6. Finalise release artefacts

- [ ] Tag the release (`git tag vX.Y.Z`) once all checks pass.
- [ ] Attach release notes, changelog excerpt, and verified hashes.
- [ ] Announce support timelines and upgrade guidance, calling out policy or
      schema changes explicitly.

Keep the checklist under version control and revise it whenever the platform
gains new capabilities or operational requirements. That way every public
release follows the same transparent playbook.
