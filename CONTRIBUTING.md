# Contributing to Noēsis

Thanks for your interest in advancing Noēsis. This project blends framework engineering with cognitive architecture research, so contributions need to be reproducible and well-instrumented by default.

> **Ethos**  
> Every step forward begins with people willing to think deeply and listen.  
> Curiosity, respect, and shared insight move us farther than raw speed.  
> If you care about reasoning, introspection, and the future of cognitive frameworks, welcome aboard.

## Quickstart
1. Fork the repository and create a feature branch.
2. Install dependencies (`uv venv && uv sync`) and verify the test suite (`uv run pytest`).
3. Develop your change, keeping artifacts (datasets, configs, checkpoints) small but shareable.

## Issues: choose the right template
- **🐞 Bug report** — runtime/CLI defects. Include dataset snapshot, schema fingerprint, faculty config, checkpoints, and the minimal repro script.
- **💡 Feature request** — new capabilities. Document the prototype entry point, required assets, success metrics, and risks.
- **📚 Documentation update** — docs/examples. Point to the source location and attach supporting notebooks, logs, or screenshots.
- **📄 Paper implementation** — map a paper into Noēsis. Provide citation, implementation plan, evaluation metrics, datasets, checkpoints, and existing replication kits.
- **🧪 Experiment / benchmark** — curriculum runs or policy deltas. Capture hypothesis, setup, sweeps, results, and artifacts.

Blank issues are disabled; discussions and exploratory ideas go to [GitHub Discussions](https://github.com/saraeloop/noesis/discussions). Our automation nudges issues missing an `## Artifacts` block, so front-load those details.

## Pull requests
- Use the PR template and delete sections that do not apply.
- Fill out the **Validation** checklist (required vs situational) and explain any unchecked items.
- Describe datasets, schema changes, checkpoints, and reproduction scripts under the relevant sections.
- Run the appropriate local checks before opening a PR:
  - `uv run pytest`
  - `pnpm install` (once) and `pnpm run build` inside `docs/` for documentation changes
  - `python scripts/pre_release.py --check-all` for CLI surface or release-impacting changes
  - Benchmark or evaluation sweeps referenced in your PR description

## Artifact checklist
- Dataset snapshot or subset (plus licensing notes)
- Schema fingerprint (`noesis schema fingerprint`) and config changes
- Faculty or pipeline configuration (TOML/JSON)
- Checkpoints or weights (trimmed if large; share hash and storage location)
- Minimal reproduction script or CLI command
- Experiment notebooks, sweeps, or dashboards when reporting metrics

## Communication & review
- Tag related issues/PRs and research papers.
- Keep discussion in the PR or linked issue for traceability; summarize any offline decisions.
- Be ready to attach extra diagnostics if reviewers request them—our automation will auto-label issues/PRs based on templates.
