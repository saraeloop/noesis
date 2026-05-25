# 🧠 Noēsis Pull Request

<!-- Keep the narrative tight—delete sections that don't apply so reviewers can focus. -->

## Overview

<!-- Describe the purpose and scope of this PR.
     What part of the cognitive framework or infrastructure does it touch? -->

## Type of Change

<!-- Select all that apply -->

- [ ] 🧩 Core framework (runtime, faculties, orchestrator, schema)
- [ ] 📈 Cognitive model or paper implementation (ReAct, Reflexion, ToT, Meta-CoT, etc.)
- [ ] 🧠 Meta-cognition or learning feedback logic
- [ ] ⚙️ Infrastructure / CI / build system
- [ ] 📚 Documentation or research notes
- [ ] 🧪 Experiment / benchmark / curriculum update
- [ ] 🧰 Developer experience (CLI, codemod, viewer, tooling)
- [ ] 🗃️ Dataset / artifact update (checkpoints, corpora, prompt packs)
- [ ] Other (please describe):

## Motivation & Context

<!-- Explain why this change is necessary.
     Is it improving fidelity, performance, or adding a new research capability? -->

## Technical Details

<!-- Summarize the main implementation aspects:
     modules changed, key functions/classes introduced,
     architectural or schema implications, and compatibility considerations. -->

## Validation

<!-- How did you verify correctness and stability? Note any deviations when a box stays unchecked. -->

### Required

- [ ] All tests pass locally (`uv run pytest`) or equivalent targeted suite
- [ ] Schema validation and export diff clean

### Situational

- [ ] Cognitive loop tested end-to-end (Observe → Learn)
- [ ] Docs build successfully (`pnpm run build` in docs/)
- [ ] CLI smoke tests pass (`python scripts/pre_release.py --check-all`)
- [ ] Benchmarks / eval sweeps reproduced
- [ ] Artifact integrity checked (hashes, licensing, storage footprint)

## ADR-003 Schema Governance Checklist

- [ ] `$schema_version` bumped for every artifact whose stable fields changed
- [ ] `docs/schema/**` regenerated (no diff after `python scripts/gen_schema.py`)
- [ ] KPI updates include version bumps plus math/clamp/rationale updates in `internal_docs/schema/kpi*.yaml`
- [ ] Relevant entry added to `MIGRATIONS.schema.md` or `MIGRATIONS.kpi.md`
- [ ] `python scripts/schema_guard.py --strict --json` passes locally
- [ ] Docs under `docs/reference/*` updated when new fields/KPIs surface to users

## Observability & Safety

<!-- Describe telemetry, insight, or policy metrics added/modified, plus any operational or alignment risks and mitigations.
     For research PRs, summarize observed gains or differences (e.g., +10 % policy_score). -->

## Educational / Research Value

<!-- If this PR implements or replicates a paper, describe:
     - Which paper or concept (cite if possible)
     - How it connects to Noēsis architecture
     - Expected insights or experiments enabled -->

- Replication kit (configs, seeds, sweeps, data access notes):

## Screenshots / Logs

<!-- Attach visuals, timeline outputs, or relevant excerpts from viewer / CLI. -->

## Related Issues / References

<!-- Link related issues, PRs, or research papers.
     Example: #42 — “Integrate Reflexion feedback loop” or (Shinn et al., 2023) -->
