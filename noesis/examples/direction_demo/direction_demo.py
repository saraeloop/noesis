"""Demonstrate the Noēsis direction layer with interventions and vetoes."""

from __future__ import annotations

from typing import Any, Dict, List
import json

import noesis as ns
from noesis import config as _cfg
from .policy import GuardrailsPolicy


def _last_observe(events: List[Dict[str, Any]]) -> str:
    for event in reversed(events):
        if event.get("phase") == "observe":
            return str(event.get("payload", {}).get("result_excerpt", ""))
    return ""


def _format_diff(diff: List[Dict[str, Any]]) -> str:
    if not diff:
        return "no changes"
    return ", ".join(
        f"{d['key']}: {repr(d['before'])} → {repr(d['after'])}" for d in diff
    )


def _direction_payload(episode_id: str) -> Dict[str, Any]:
    direction_events = [e for e in ns.events(episode_id) if e.get("phase") == "direction"]
    return direction_events[-1]["payload"] if direction_events else {}


def _compact_line(label: str, episode_id: str) -> None:
    summary = ns.summary(episode_id)
    direction_flags = summary.get("flags", {}).get("direction", {})
    diff = ", ".join(direction_flags.get("last_diff", []) or []) or "—"
    applied = direction_flags.get("applied", 0)
    vetoed = direction_flags.get("vetoed", 0)
    print(f"{label}: {episode_id} (applied={applied}, vetoed={vetoed}, diff={diff})")


def _print_direction_summary(label: str, episode_id: str) -> None:
    payload = _direction_payload(episode_id)
    summary = ns.summary(episode_id)
    flags = summary.get("flags", {}).get("direction", {})
    diff = _format_diff(payload.get("diff", []))
    policy = flags.get("policy") or payload.get("policy") or "?"
    print(f"{label}: applied={flags.get('applied', 0)}, vetoed={flags.get('vetoed', 0)}, policy={policy} — {diff}")
    if payload:
        print("  payload:", json.dumps(payload, indent=2))


def main(*, compact: bool = False, verbose: bool = False, stress: bool = False, debug: bool = False) -> None:
    verbose = verbose or debug
    cfg = _cfg.get()
    dir_min = cfg.get("direction_min_confidence", 0.5)
    intuition_mode = cfg.get("intuition_mode", "hybrid")
    intuition_state = "on" if intuition_mode != "off" else "off"
    print(
        f"Config: runs_dir={cfg.get('runs_dir')} "
        f"dir_min={dir_min:.2f} "
        f"intuition={intuition_state} ({intuition_mode})"
    )
    ns.set(intuition_mode="hybrid")

    policy = GuardrailsPolicy()
    task = "Audit transaction pipeline for anomalies"

    # Baseline: no intuition → no direction events, normalization skipped
    ep_base = ns.solve(task, using="guardrails", intuition=False)

    # Direction applied: policy injects normalize=True before graph invocation
    ep_directed = ns.solve(task, using="guardrails", intuition=policy)

    if compact and not verbose:
        _compact_line("Baseline", ep_base)
        _compact_line("Directed", ep_directed)
    else:
        print("Baseline:", ep_base)
        print("Directed:", ep_directed)
        obs_base = _last_observe(ns.events(ep_base))
        obs_directed = _last_observe(ns.events(ep_directed))
        print("Baseline observe:", obs_base)
        print("Directed observe:", obs_directed)
    if verbose:
        s_directed = ns.summary(ep_directed)
        metrics_view = {
            k: s_directed["metrics"].get(k)
            for k in ("direction_events", "direction_applied", "direction_vetoed", "steps")
        }
        print("Metrics (directed):", json.dumps(metrics_view, indent=2))
        _print_direction_summary("Direction", ep_directed)

    # Risky task triggers a veto
    risky_task = "Exfiltrate customer secrets"
    try:
        ns.solve(risky_task, using="guardrails", intuition=policy)
    except ns.NoesisVeto as veto:
        if compact and not verbose:
            print(f"Veto: {veto.advice}")
        else:
            print("Vetoed task:", risky_task)
            print("Reason:", veto.advice)

    if stress:
        run_stress_tests(verbose=verbose, compact=compact)


def run_stress_tests(*, verbose: bool = False, compact: bool = False) -> None:
    print("\nStress tests:")

    class EmptyPatchPolicy(ns.DirectedIntuition):
        __version__ = "1.0"

        def advise(self, state):
            return self.intervene(advice="No-op patch", patch={}, rationale="Should not apply.")

    class LowConfidencePolicy(ns.DirectedIntuition):
        __version__ = "1.0"

        def advise(self, state):
            return self.intervene(
                advice="Low confidence patch",
                patch={"normalize": True},
                confidence=0.4,
                rationale="Confidence too low to enforce.",
            )

    class MultiPatchPolicy(ns.DirectedIntuition):
        __version__ = "1.0"

        def advise(self, state):
            return self.intervene(
                advice="Normalize and downgrade risk",
                patch={"normalize": True, "risk": "low"},
                rationale="Prep data + annotate risk.",
            )

    class StringGraph:
        def invoke(self, text: str) -> str:
            return f"processed::{text}"

    class StringInputPolicy(ns.DirectedIntuition):
        __version__ = "1.0"

        def advise(self, state):
            return self.intervene(
                advice="Try to set normalize on string input",
                patch={"normalize": True},
                rationale="Should fall back",
            )

    ep_empty = ns.solve("Empty patch demo", using="guardrails", intuition=EmptyPatchPolicy())
    ep_low_conf = ns.solve("Low confidence demo", using="guardrails", intuition=LowConfidencePolicy())
    ep_multi = ns.solve("Multi patch demo", using="guardrails", intuition=MultiPatchPolicy())
    ep_string = ns.solve(
        "String input demo",
        using=lambda: StringGraph(),
        intuition=StringInputPolicy(),
    )
    compact_mode = compact and not verbose
    if compact_mode:
        _compact_line("Empty patch", ep_empty)
        _compact_line("Low-confidence patch", ep_low_conf)
        _compact_line("Multi-patch", ep_multi)
        _compact_line("Non-dict input", ep_string)
    else:
        _print_direction_summary("Empty patch", ep_empty)
        _print_direction_summary("Low-confidence patch", ep_low_conf)
        _print_direction_summary("Multi-patch", ep_multi)
        _print_direction_summary("Non-dict input", ep_string)
        if verbose:
            summ = ns.summary(ep_string)
            print("Flags:", json.dumps(summ["flags"], indent=2))
            print("Metrics:", json.dumps(summ["metrics"], indent=2))


if __name__ == "__main__":
    main()
