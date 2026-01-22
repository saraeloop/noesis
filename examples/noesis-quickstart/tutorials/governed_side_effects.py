"""
Tutorial: Governed Side Effects (Noesis)

Goal
- Demonstrate the OS-boundary event order:
  action_candidate → governance → act (or terminate on veto).
- Show enforced veto behavior with no act events.

Run:
  uv run python -m tutorials.governed_side_effects
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse

import noesis as ns
from noesis.exceptions import NoesisVeto

from common.reporting import (
    print_completion,
    print_results_summary_episode,
    print_results_summary_header,
)
from common.console import headline, error, info
from common.episode_io import episode_dir
from common.errors import QuickstartError


def run_shell(*, command: str, cwd: str | None = None, timeout_ms: int | None = None) -> dict[str, Any]:
    """Trivial shell executor used by governed_act in this tutorial."""
    _ = (cwd, timeout_ms)
    return {"stdout": "ok", "stderr": "", "exit_code": 0, "command": command}


def _episode_ids(runs_dir: Path) -> set[str]:
    if not runs_dir.exists():
        return set()
    return {p.name for p in runs_dir.iterdir() if p.is_dir() and p.name.startswith("ep_")}


def _detect_new_episode(before: set[str], after: set[str], runs_dir: Path) -> str | None:
    new_ids = list(after - before)
    if not new_ids:
        return None
    if len(new_ids) == 1:
        return new_ids[0]
    newest = max(new_ids, key=lambda eid: (runs_dir / eid).stat().st_mtime)
    return newest


def _with_governance_mode(mode: str, fn):  # type: ignore[no-untyped-def]
    prev = ns.get().get("governance_mode", "off")
    ns.set(governance_mode=mode)
    try:
        return fn()
    finally:
        ns.set(governance_mode=prev)


def run_governed_action(
    *,
    goal: str,
    command: str,
    runs_dir: Path,
    cwd: str | None = None,
) -> tuple[str | None, str]:
    """Run a governed action and return (episode_id, outcome_label)."""
    before = _episode_ids(runs_dir)
    # governed_act writes its own episode bundle; we locate it by diffing runs_dir.
    try:
        result = _with_governance_mode(
            "enforce",
            lambda: ns.governed_act(
                goal=goal,
                kind="shell",
                payload={"command": command, "cwd": cwd, "timeout_ms": 2000},
            ),
        )
        outcome = f"ok: {result}"
    except NoesisVeto as veto:
        outcome = f"vetoed: {veto.advice}"
    after = _episode_ids(runs_dir)
    episode_id = _detect_new_episode(before, after, runs_dir)
    return episode_id, outcome


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Governed side effects tutorial (no LLM).")
    return parser.parse_args()


def _summarize_episode(episode_id: str) -> dict[str, Any]:
    events = list(ns.events.read(episode_id))
    act_count = sum(1 for e in events if e.get("phase") == "act")
    gov = next((e for e in events if e.get("phase") == "governance"), None)
    decision = None
    if gov and isinstance(gov.get("payload"), dict):
        decision = gov["payload"].get("decision")
    term = next((e for e in events if e.get("phase") == "terminate"), None)
    status = None
    if term and isinstance(term.get("payload"), dict):
        status = term["payload"].get("status")
    return {"act_count": act_count, "decision": decision, "terminate": status}


def main() -> int:
    _parse_args()
    headline("Governed Side Effects")

    try:
        headline("WHAT YOU GET")
        print("- A deterministic proof of veto semantics (no act events on veto)")
        print("- Action-candidate governance traces you can inspect and diff")

        headline("HOW TO RUN")
        print("- uv run python -m tutorials.governed_side_effects")

        ns.set(governance_mode="enforce")
        ns.set(shell_executor=run_shell)

        runs_dir = Path(ns.get().get("runs_dir", ".noesis/episodes"))
        info("governed_act writes a separate episode; we locate it by diffing runs_dir.")
        info("Verify is skipped for governed_act episodes (no workspace snapshots).")

        results: dict[str, str | None] = {}
        outcomes: dict[str, str] = {}

        episode_id, outcome = run_governed_action(
            goal="List files under /tmp/noesis-demo.",
            command="ls -a /tmp/noesis-demo",
            runs_dir=runs_dir,
            cwd="/tmp",
        )
        results["gov_allow"] = episode_id
        outcomes["gov_allow"] = outcome

        episode_id, outcome = run_governed_action(
            goal="Delete temporary cache files under /tmp/noesis-demo.",
            command="rm -rf /tmp/noesis-demo/cache",
            runs_dir=runs_dir,
            cwd="/tmp",
        )
        results["gov_audit"] = episode_id
        outcomes["gov_audit"] = outcome

        episode_id, outcome = run_governed_action(
            goal="Destroy all data in the production database.",
            command="rm -rf /prod-data",
            runs_dir=runs_dir,
        )
        results["gov_veto"] = episode_id
        outcomes["gov_veto"] = outcome

        print_results_summary_header()
        for label, episode_id in results.items():
            if episode_id:
                info(f"Governed {label} outcome: {outcomes.get(label, 'unknown')}")
                print_results_summary_episode(label, episode_id)
                summary = _summarize_episode(episode_id)
                print(f"  decision: {summary.get('decision')}")
                print(f"  act_count: {summary.get('act_count')}")
                print(f"  terminate: {summary.get('terminate')}")

        example_id = results.get("gov_veto") or next((v for v in results.values() if v), None)
        if example_id:
            ep_dir = episode_dir(runs_dir, example_id)
            headline("WHERE TO LOOK")
            print(f"- events.jsonl: {ep_dir / 'events.jsonl'} (action_candidate + governance decision)")
            print(f"- summary.json: {ep_dir / 'summary.json'} (metrics.veto_count, metrics.success)")
            print(f"- manifest.json: {ep_dir / 'manifest.json'} (hash ledger)")
            print(f"- final.json: {ep_dir / 'final.json'} (if present, sealed outcome)")

            headline("WHAT IT MEANS")
            print("- Vetoed episodes have act_count=0 and terminate.status='vetoed'.")
            print("- Allowed/audit episodes have act_count>0 and terminate.status='ok'.")

        print_completion("Governed side effects tutorial completed.")
        return 0

    except QuickstartError as e:
        error(str(e))
        return 2
    except Exception as e:
        error(f"Unexpected failure: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
