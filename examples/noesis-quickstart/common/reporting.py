from __future__ import annotations

from typing import Any, Iterable

from common.console import headline, info, success, warn
from common.episode_io import read_events_jsonl, read_summary_json, summarize_timeline


def print_intro_trace_evals() -> None:
    """Print the tutorial intro for trace-based evals."""
    headline("Trace-Based Evals: Safety & Success (Single File)")
    print(
        """
This tutorial scores behavior from artifacts, not just final answers.

Canonical signals:
- Enforced veto is determined by Governance:
    phase="governance", payload.decision="veto", payload.enforced=true
- On enforce+veto runs, you should see:
    plan → direction(blocked) → governance(veto) → terminate(vetoed)
  and there are NO act events.

Two policy levers:
  - Built-in Governance (PreActGovernor) = enforcement + canonical veto artifacts
  - Custom Intuition policy = advisory signals only, no veto
"""
    )


def print_dataset(rows: Iterable[dict[str, Any]]) -> None:
    """Print the Dataset section with cases to be evaluated."""
    headline("Dataset")
    for r in rows:
        info(f'{r["id"]}: {r["kind"]} — {r["prompt"]}')


def print_run_results(rows: Iterable[dict[str, Any]]) -> None:
    """Print the Run section with episode ids."""
    headline("Run")
    for r in rows:
        success(f'{r["id"]} → {r["episode_id"]}')


def print_episode_flags(flags_rows: Iterable[dict[str, Any]]) -> None:
    """Print per-episode flags for evals."""
    headline("Per-episode flags")
    for r in flags_rows:
        info(
            f'{r["id"]} ({r["kind"]}) → '
            f'vetoed={r["vetoed"]} success={r["success"]} '
            f'act_count={r["act_count"]} terminate={r["terminate_status"]}'
        )


def print_intro_guarded_langgraph() -> None:
    """Print the tutorial intro for the guarded LangGraph demo."""
    headline("Governance Tutorial: Pre-Act Veto")
    print(
        """
This tutorial demonstrates Noēsis Governance in front of a real (LLM-backed) LangGraph plan→act agent.

Two policy levers:
  - Built-in Governance (PreActGovernor) = enforcement + canonical veto artifacts
  - Custom Intuition policy (PathRiskSignals) = advisory hints only (no veto)

Expected behavior:
  - allow/audit: LangGraph act runs (LLM is called)
  - veto: governance blocks BEFORE act (no act events)
"""
    )


def print_case_intro(label: str, task: str) -> None:
    """Print a case header and task description."""
    headline(f"Case: {label}")
    info(f"Task: {task}")


def print_case_result(episode_id: str | None) -> None:
    """Print the case episode id (or a warning if unavailable)."""
    if episode_id:
        success(f"Episode ID: {episode_id}")
    else:
        warn("Episode ID: unavailable")


def print_results_summary_header() -> None:
    """Print the Results Summary header."""
    headline("Results Summary")


def print_results_summary_episode(label: str, episode_id: str) -> None:
    """Print a results summary section header for one episode."""
    print(f"\n{'='*60}")
    print(f"Episode: {label} ({episode_id})")
    print(f"{'='*60}")


def print_next_steps(results: dict[str, str | None]) -> None:
    """Print the Next Steps section for tutorial runs."""
    headline("Next Steps")
    for label, episode_id in results.items():
        if episode_id:
            info(f"View {label}: uv run noesis view {episode_id}")


def print_completion(message: str) -> None:
    """Print a final success message for a tutorial run."""
    success(message)


def print_results_header_guarded() -> None:
    headline("Results Summary")


def print_case(label: str, task: str, episode_id: str | None) -> None:
    info(f"Case {label}: {task}")
    if episode_id:
        success(f"Episode ID: {episode_id}")
    else:
        warn("Episode ID: unavailable")


def print_guarded_episode_results(episode_id: str, runs_dir: str = ".noesis/episodes") -> None:
    try:
        events = read_events_jsonl(runs_dir=runs_dir, episode_id=episode_id, limit=80)
        summary = read_summary_json(runs_dir=runs_dir, episode_id=episode_id)
    except FileNotFoundError:
        warn(f"Artifacts not found for {episode_id}")
        return

    print("\n  Timeline:")
    for verb, status in summarize_timeline(events, limit=20):
        print(f"    [{verb:<12}] {status}")

    insight = summary.get("insight") if isinstance(summary.get("insight"), dict) else {}
    insight_metrics = insight.get("metrics") if isinstance(insight.get("metrics"), dict) else {}
    latencies = insight_metrics.get("latencies") if isinstance(insight_metrics.get("latencies"), dict) else {}
    time_to_veto_ms = latencies.get("time_to_veto_ms")

    gov_events = [e for e in events if e.get("phase") == "governance"]
    if gov_events:
        print("\n  Governance Events:")
        for gov in gov_events:
            payload = gov.get("payload", {}) if isinstance(gov.get("payload"), dict) else {}
            decision = payload.get("decision", "unknown")
            rule_id = payload.get("rule_id", "unknown")
            message = payload.get("message", "")
            enforced = payload.get("enforced", False)
            mode = payload.get("mode", "unknown")
            policy_id = payload.get("policy_id")
            policy_version = payload.get("policy_version") or "unknown"

            verdict = "VETO" if decision == "veto" else "AUDIT" if decision == "audit" else "ALLOW"
            print(f"    {verdict}")
            print(f"       rule_id: {rule_id}")
            print(f"       mode: {mode}")
            print(f"       enforced: {enforced}")
            if decision == "veto" and policy_id:
                print(f"       policy: {policy_id}@{policy_version}")
            if decision == "veto" and time_to_veto_ms is not None:
                print(f"       time_to_veto_ms: {time_to_veto_ms}")
            if message:
                print(f"       message: {message}")
    else:
        print("\n  Governance: (no governance events)")

    act_events = [e for e in events if e.get("phase") == "act"]
    print(f"\n  Act events: {len(act_events)}")

    term_events = [e for e in events if e.get("phase") == "terminate"]
    for t in term_events:
        payload = t.get("payload", {}) if isinstance(t.get("payload"), dict) else {}
        status = payload.get("status", "unknown")
        print(f"  Terminate status: {status}")

    metrics = summary.get("metrics", {}) if isinstance(summary.get("metrics"), dict) else {}
    print("\n  Metrics:")
    print(f"    success: {metrics.get('success', '?')}")
    print(f"    veto_count: {metrics.get('veto_count', 0)}")


def print_flags(rows: Iterable[dict[str, Any]]) -> None:
    for row in rows:
        flags = row.get("flags")
        if not flags:
            warn(f'{row.get("id", "?")}: flags unavailable')
            continue
        info(
            f'{row.get("id")} ({row.get("kind")}) -> '
            f"vetoed={flags.vetoed} success={flags.success} "
            f"act_count={flags.act_count} terminate={flags.terminate_status}"
        )


def print_aggregate(score: dict[str, Any], avg_act_phase_ms: float | None) -> None:
    headline("Aggregate score")
    info(f'safety_pass_rate: {score["safety_pass_rate"]:.2f} ({score["unsafe_total"]} unsafe)')
    info(f'task_success_rate: {score["task_success_rate"]:.2f} ({score["safe_total"]} safe)')

    if avg_act_phase_ms is None:
        warn("avg_act_phase_ms: unavailable")
    else:
        info(f"avg_act_phase_ms: {avg_act_phase_ms:.1f}")
