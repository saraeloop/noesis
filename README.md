[![PR Contracts](https://github.com/saraeloop/noesis/actions/workflows/pr-contracts.yml/badge.svg)](https://github.com/saraeloop/noesis/actions/workflows/pr-contracts.yml)
[![Stars](https://img.shields.io/github/stars/saraeloop/noesis?style=social)](https://github.com/saraeloop/noesis/stargazers)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/saraeloop/noesis)
[![Planner Modes](https://img.shields.io/badge/planner-meta%20%E2%80%A2%20minimal-0ea5e9)](#how-it-works)
[![Python](https://img.shields.io/badge/python-3.11+-18181b)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache%202.0-64748b)](LICENSE)

# Noēsis (νόησις)

_Understanding, made observable._

Noēsis is a cognitive runtime for agent workflows. It turns each run into an auditable episode with a causal event chain, governed side effects, and resumable execution.

Each run produces a structured artifact pack (`events.jsonl`, `summary.json`, `state.json`, `manifest.json`) that can be inspected, audited, and verified.

Bring your own graphs, loops, tools, and prompts. Noēsis adds runtime evidence, verification, and governance boundaries without replacing your orchestrator or agent framework.

## Runtime boundary

```mermaid
flowchart TD
    A["Your agent / graph / workflow"] --> B["Noēsis runtime"]
    B --> C["events.jsonl"]
    B --> D["summary.json"]
    B --> E["state.json"]
    B --> F["final.json"]
    B --> G["manifest.json"]
    B --> H["governed side effects"]
    B --> I["interrupt / checkpoint / resume"]
```

## The problem

Agent frameworks can plan, call tools, mutate files, and take action across many steps. When something goes wrong, most teams still lack a durable, trustworthy record of what actually happened.

Two bad options:

- trust the framework's internal state
- build your own tracing, governance, and continuation layer

Noēsis gives you a third option: keep your orchestrator, but run it inside a runtime that records cognition, governs side effects, and preserves resumable execution.

## What Noēsis does

- **structured episodes**: every run emits `events.jsonl`, `summary.json`, `state.json`, `final.json`, and `manifest.json`
- **governed side effects**: review, audit, veto, or pause actions before they execute
- **resumable execution**: interrupt, checkpoint, and continue the same run
- **verification**: capture workspace evidence and assert expected changes
- **framework-agnostic integration**: wrap your own graphs, adapters, and workflows

## Minimal example

```python
import noesis as ns

episode_id = ns.run("Draft a weekly engineering update", intuition=True)

summary = ns.summary.read(episode_id)
timeline = list(ns.events.read(episode_id))

print(summary["metrics"]["success"])
print(timeline[0]["phase"], timeline[0].get("payload"))
```

## How it works

Noēsis models each run as explicit cognition phases:

**Observe -> Interpret -> Plan -> Govern -> Act -> Reflect -> Learn**

Each phase emits typed events with `caused_by` linkage, so the artifact trail preserves how the run moved from observation to action and reflection.

## Flow at a glance

```mermaid
flowchart LR
    subgraph "Observe & Interpret"
        O["observe events"] --> I["intuition hints"]
    end
    I --> P{"direction / plan"}
    P -->|governed| A["act / tool call"]
    A --> R["reflect"]
    R --> L["learn signal"]
    L --> M["memory + insight"]
    M --> O
```

## Artifact layout

By default, Noēsis writes artifacts under `.noesis/episodes/`:

```text
.noesis/
  episodes/
    ep_.../
      events.jsonl
      summary.json
      state.json
      final.json
      manifest.json
      learn.jsonl     # optional
      prompts.jsonl   # optional
      snapshots/
        pre.json
        post.json
```

## Governed side effects

```python
import noesis as ns
from noesis.exceptions import NoesisVeto


def run_shell(*, command: str, cwd: str | None = None, timeout_ms: int | None = None):
    return {"stdout": "ok", "stderr": "", "exit_code": 0, "command": command}


ns.set(
    shell_executor=run_shell,
    governance_mode="enforce",
    governance_pause_on_veto=True,
)

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
    print(f"Blocked by governance: {veto.advice}")
```

## Workspace verification

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
    workspace=".",
    verify=verify,
)
```

## Pause, checkpoint, and continue

```python
import noesis as ns

ns.set(governance_mode="enforce", governance_pause_on_veto=True)

episode_id = ns.solve("Danger operation: delete production database", using=my_graph)

interrupt_id = ns.interrupt(episode_id, reason="awaiting approval")
checkpoint = ns.checkpoint(episode_id, caused_by=interrupt_id)

ns.resume(episode_id, checkpoint_id=checkpoint["checkpoint_id"])

episode_id = ns.resume_run(
    episode_id,
    checkpoint_id=checkpoint["checkpoint_id"],
    using=my_graph,
)
```

Rule of thumb:

- `resume()` emits lifecycle evidence only
- `resume_run()` emits `run.resume` and continues execution

## Install

Python >= 3.11.

```bash
git clone https://github.com/saraeloop/noesis.git
cd noesis
uv tool install .
# or: pipx install .
```

Run the demo:

```bash
uv run python examples/demo.py
```

## Who it's for

**Builders / platform teams**: wrap LangGraph, CrewAI, or custom graphs with observable cognition and governed execution without rewriting your orchestrator.

**Applied researchers**: collect structured traces for benchmarks, ablations, evaluation, and papers.

**Ops / compliance / platform governance**: review immutable JSON artifacts showing what happened, what changed, and why side effects were allowed or blocked.

**Anyone deploying agents that act on real systems**: file writes, shell execution, API calls, config changes.

## Docs and links

- Artifacts guide: `docs/artifacts/state.md`
- Schema index: `docs/app/reference/schema-index.mdx`
- CLI reference: `docs/app/reference/cli/page.mdx`
- Quickstart guide: `docs/app/guides/quickstart/page.mdx`
- Examples: `examples/README.md`

## Status

- Package: `noesis` v1.0.0
- Schema pack: summary/state/events/kpi v1.0.0
- Python: >= 3.11
- CI: contracts, schema guard, and release preparation run in GitHub Actions

## Community and support

Issues and discussions live on GitHub. Contributions are welcome. See `CONTRIBUTING.md`.

## Security

Report vulnerabilities privately through GitHub Security Advisories. See `SECURITY.md`.

## License

Apache 2.0. See `LICENSE`.

Copyright 2025 Sara Loera
