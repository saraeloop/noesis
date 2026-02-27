[![PR Contracts](https://github.com/saraeloop/noesis/actions/workflows/pr-contracts.yml/badge.svg)](https://github.com/saraeloop/noesis/actions/workflows/pr-contracts.yml)
[![Stars](https://img.shields.io/github/stars/saraeloop/noesis?style=social)](https://github.com/saraeloop/noesis/stargazers)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/saraeloop/noesis)
[![Planner Modes](https://img.shields.io/badge/planner-meta%20%E2%80%A2%20minimal-0ea5e9)](#core-concepts)
[![Python](https://img.shields.io/badge/python-3.11+-18181b)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache%202.0-64748b)](LICENSE)
# Noēsis (νόησις)

_Understanding, made observable._

Noēsis is a lightweight cognitive control layer for agent workflows: each run becomes an auditable episode with immutable, structured artifacts and optional governance for side effects.

Bring your own graphs, loops, and tools. Noēsis adds observability, verification, and governance boundaries—without replacing your orchestrator or agent framework.

## Who it’s for
- **Builders / platform teams:** wrap LangGraph, CrewAI, or custom graphs with cognition without rewrites.
- **Applied researchers:** collect structured traces for benchmarks, ablations, and papers.
- **Product & GTM:** point to concrete KPIs (plan adherence, veto count, tool coverage).
- **Ops & compliance:** review immutable JSON traces showing what happened and why it was allowed.

## Why Noēsis?

| Proof point | What it gives you |
| --- | --- |
| **Observable cognition** | Each run emits `summary.json`, `state.json`, and `events.jsonl` for replay and evaluation. |
| **Direction + guardrails** | Planner modes (`meta` vs `minimal`) layer planning and governance over any agent graph. |
| **Durable memory** | Plug in SQLite/FAISS/HNSW (or your own provider) so episodes learn across time. |
| **Learning signals** | Insight metrics and `learn.emit(...)` provide structured payloads for audits and tuning. |

## Core concepts
- Phases: **Observe → Interpret → Plan → Govern → Act → Reflect → Learn**

Flow at a glance:

```mermaid
flowchart LR
    subgraph Observe & Interpret
        O[observe events] --> I[intuition hints]
    end
    I --> P{Direction plan}
    P -->|governed| A[act / tool call]
    A --> R[reflect]
    R --> L[learn signal]
    L --> M[memory + insight]
    M --> O
```

- Artifacts (under `.noesis/episodes/<episode_id>/` by default; set `runs_dir` to add a label):
  - `events.jsonl` – timeline with causal IDs
  - `summary.json` – metrics, outcome, cross-links
  - `state.json` – current plan and episode state
  - `manifest.json` – SHA-256 + size ledger for tamper evidence
  - `learn.jsonl` (optional) – learning payloads

## Quickstart
> Python ≥ 3.11. Source-first.

Install and run a demo:

```bash
# clone
git clone https://github.com/saraeloop/noesis.git
cd noesis

# install console script from source
uv tool install .
# or: pipx install .

# optional for pretty JSON in CLI examples
brew install jq
```

Minimal run (emits artifacts to `./.noesis/episodes` by default):

```python
import noesis as ns

episode_id = ns.run("Draft a weekly engineering update", intuition=True)
summary = ns.summary.read(episode_id)
timeline = list(ns.events.read(episode_id))

print(summary["metrics"]["success"])
print(timeline[0]["phase"], timeline[0].get("payload"))
```

Artifacts layout:

```
.noesis/
  episodes/
    ep_.../          # episode id
      summary.json
      state.json
      events.jsonl
      manifest.json
      learn.jsonl    # optional
      prompts.jsonl  # optional, prompt provenance (opt-in)
```

For a fuller tour: `uv run python examples/demo.py`

## Bring your own agent / graph
Noēsis is framework-agnostic—decorate your orchestrator and keep your tools/prompts:

```python
from pathlib import Path
import noesis as ns

episode_id = ns.solve(
    "Generate release notes from ./CHANGELOG.md",
    using=lambda: Path("flows/release_notes.py"),  # your graph/runner
    intuition=True,
)
```

Toggle governance depth:

```python
import noesis as ns

ns.set(runs_dir="./.noesis/episodes/demo")
ns.set(planner_mode="meta")      # with governance (default)
ns.run("Summarize release notes", intuition=False)

ns.set(planner_mode="minimal")   # opt out for throughput
ns.run("Summarize release notes", intuition=False)
```

Workspace snapshots + verification (verify real filesystem changes with immutable snapshots):

```python
import noesis as ns

verify = [
    ns.file_exists("config.yaml"),
    ns.file_contains("config.yaml", "enabled: true"),
    ns.only_modified(["config.yaml"]),
]

episode_id = ns.solve(
    "Update config",
    using="my.module:adapter_fn",
    workspace=".",   # capture pre/post workspace snapshots
    verify=verify,
)
```

Config snapshots (read/write current session config):

```python
import noesis as ns

ns.set(runs_dir="./.noesis/episodes/demo", planner_mode="minimal", governance_mode="audit")
config = ns.get()
print(config["runs_dir"], config["planner_mode"])
```

Governed side effects (pre-act gating):

ns.governed_act(...) is the “operating-system boundary” for side effects. It emits:
	•	action_candidate → governance → act
	•	or, on enforced veto: action_candidate → governance → terminate (no act)

```python
import noesis as ns
from noesis.exceptions import NoesisVeto

def run_shell(*, command: str, cwd: str | None = None, timeout_ms: int | None = None):
    return {"stdout": "ok", "stderr": "", "exit_code": 0, "command": command}

ns.set(shell_executor=run_shell)

try:
    result = ns.governed_act(
        goal="List repository files",
        kind="shell",
        payload={
            "command": "ls -a",
            "cwd": ".",
            "timeout_ms": 2000,
        },
    )
    print(result)
except NoesisVeto as veto:
    # Raised only when governance is enforcing and the action is vetoed.
    print(f"Blocked by governance: {veto.advice}")
```

## Docs & links
- Artifacts guide: `docs/artifacts/state.md`
- Runs cheat sheet: `docs/explanation/artifacts.mdx`
- Schema index: `docs/app/reference/schema-index.mdx`
- CLI reference: `docs/app/reference/cli/page.mdx`
- Quickstart guide: `docs/app/guides/quickstart/page.mdx`
- Examples overview: `examples/README.md`

## Versioning & stability
- Package: `noesis` v1.0.0
- Schema pack: summary/state/events/kpi v1.0.0
- Python: ≥ 3.11
- CI: contracts, schema guard, and release prep run in GitHub Actions

## Community & support
- Issues and discussions on GitHub.
- Contributions welcome—see `CONTRIBUTING.md`.

## Security
- Please report vulnerabilities privately via GitHub security advisories; see `SECURITY.md` for the full policy.

## License
Apache 2.0. See `LICENSE` © 2025 Sara Loera
