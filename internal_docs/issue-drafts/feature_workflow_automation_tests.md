# Feature Request: Add workflow lint and dry-run coverage for GitHub Actions

## Overview
Prevent regressions in `.github/workflows/*` and `.github/ISSUE_TEMPLATE/*` by adding automated linting/dry-run checks that validate required headings and label usage.

## Motivation
- Current automation (issue triage + artifact nudges) has no CI coverage; regex drift or missing labels will only surface after merge.
- Offline contributors need a reproducible way to verify workflow changes without triggering GitHub Actions.

## Proposed Implementation
- Prototype entry point: `pnpm run workflow:lint` or `uv run scripts/check_workflows.py`.
- Required assets: actionlint binary (via `brew` or GitHub Action), optional `act` config for local simulation.
- Migration considerations: ensure the lint step runs quickly and can be skipped locally (`SKIP_ACTIONLINT=1`).

## Related Components
- [ ] Runtime / Faculties
- [x] CLI / Viewer
- [x] Schema / Config
- [ ] Learning / Insight
- [x] Infrastructure / CI
- [ ] Evaluation / Benchmarks
- [x] Safety / Alignment guardrails

## Success Criteria & Measurement
- Benchmarks: CI job fails when templates lack `## Artifacts` or workflows reference missing labels.
- Baseline: manual review only.
- Telemetry: upload lint logs as artifacts for debugging.

## Safety & Risk
- Keep lint job optional for forks without `act` installed; document override flags.

## Artifacts & Research Assets
- actionlint config or script.
- Sample failing/passing workflow fixtures.
- Update to CONTRIBUTING.md with instructions.

## Additional Context
- Complements `.github/workflows/issue-artifacts-nudge.yml` and `.github/workflows/issue-triage.yml` to guarantee long-term reliability.
