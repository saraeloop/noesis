"""
Governance Tutorial: Pre-Act Veto of Dangerous Operations

Goal
- Demonstrate the Governance faculty vetoing dangerous operations
- See governance events with decision="veto" in the trace
- See the episode terminate with status="vetoed" and no act events

The Governance faculty runs AFTER planning, BEFORE acting:
  observe → intuition → interpret → plan → direction → governance → act

When governance vetoes:
- Emits governance event with decision="veto"
- Emits terminate event with status="vetoed"  
- No act events are emitted

Run:
  uv run python -m tutorials.guarded_langgraph
"""

from __future__ import annotations

import os
from typing import Any

from common.console import headline, info, success, warn, error
from common.config import load_dotenv_if_present, require_openai_key, import_noesis
from common.episode_io import episode_dir, read_events_jsonl, read_summary_json, summarize_timeline
from common.errors import QuickstartError


# -----------------------------
# Run cases and display results
# -----------------------------

def run_case(ns: Any, task: str, label: str) -> str | None:
    """
    Run a single episode using ns.run() which goes through EpisodeRunner
    and evaluates the built-in PreActGovernor.
    
    Built-in PreActGovernor rules:
    - VETO: "danger", "veto", "destroy", "shutdown", "wipe"
    - AUDIT: "write", "delete", "drop"
    - ALLOW: everything else
    """
    headline(f"Case: {label}")
    info(f"Task: {task}")
    
    try:
        # Use ns.run() which goes through EpisodeRunner with governance
        episode_id = ns.run(
            task,
            intuition=True,
            tags={"tutorial": "governance", "case": label},
        )
        success(f"Episode ID: {episode_id}")
        return episode_id
    except Exception as e:
        error(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def show_episode_results(episode_id: str, runs_dir: str = "runs") -> None:
    """Display results for an episode, focusing on governance events."""
    try:
        events = read_events_jsonl(runs_dir=runs_dir, episode_id=episode_id, limit=50)
        summary = read_summary_json(runs_dir=runs_dir, episode_id=episode_id)
    except FileNotFoundError:
        warn(f"Artifacts not found for {episode_id}")
        return
    
    # Timeline summary
    print("\n  Timeline:")
    for verb, status in summarize_timeline(events, limit=15):
        print(f"    [{verb:<12}] {status}")
    
    # Governance events (the key output)
    gov_events = [e for e in events if e.get("phase") == "governance"]
    if gov_events:
        print("\n  Governance Events:")
        for gov in gov_events:
            payload = gov.get("payload", {})
            decision = payload.get("decision", "unknown")
            rule_id = payload.get("rule_id", "unknown")
            message = payload.get("message", "")
            enforced = payload.get("enforced", False)
            mode = payload.get("mode", "unknown")
            
            if decision == "veto":
                print(f"    ⛔ VETO")
            elif decision == "audit":
                print(f"    ⚠️  AUDIT")
            else:
                print(f"    ✅ ALLOW")
            
            print(f"       rule_id: {rule_id}")
            print(f"       mode: {mode}")
            print(f"       enforced: {enforced}")
            if message:
                print(f"       message: {message}")
    else:
        print("\n  Governance: (no governance events)")
    
    # Check for act events (should be absent on veto)
    act_events = [e for e in events if e.get("phase") == "act"]
    print(f"\n  Act events: {len(act_events)}")
    
    # Check for terminate event
    terminate_events = [e for e in events if e.get("phase") == "terminate"]
    for t in terminate_events:
        payload = t.get("payload", {})
        status = payload.get("status", "unknown")
        print(f"  Terminate status: {status}")
    
    # Summary metrics
    metrics = summary.get("metrics", {})
    print(f"\n  Metrics:")
    print(f"    success: {metrics.get('success', '?')}")
    print(f"    veto_count: {metrics.get('veto_count', 0)}")


# -----------------------------
# Main
# -----------------------------

def main() -> int:
    headline("Governance Tutorial: Pre-Act Veto")
    
    print("""
This tutorial demonstrates the Governance faculty:

  observe → intuition → interpret → plan → direction → governance → act
                                              ↑
                                        We are here
                              
The built-in PreActGovernor evaluates goal + plan against rules:

  VETO:  "danger", "veto", "destroy", "shutdown", "wipe"
  AUDIT: "write", "delete", "drop"
  ALLOW: everything else

When governance mode is "enforce" and decision is "veto":
  - Governance event emitted with decision="veto", enforced=true
  - Episode terminates with status="vetoed"
  - NO act events are emitted (execution blocked)
""")
    
    try:
        load_dotenv_if_present()
        require_openai_key()
        
        ns = import_noesis()
        
        # Configure governance
        # - planner_mode="meta" enables Direction + Governance phases
        # - governance_mode="enforce" means VETO blocks execution
        ns.set(planner_mode="meta", governance_mode="enforce")
        
        results = {}
        
        # --- Case 1: ALLOW (no trigger words) ---
        results["allow"] = run_case(
            ns,
            task="List all available resources in the system",
            label="allow",
        )
        
        # --- Case 2: AUDIT (contains "delete" - triggers audit) ---
        results["audit"] = run_case(
            ns,
            task="Delete the temporary cache files",
            label="audit",
        )
        
        # --- Case 3: VETO (contains "destroy" - triggers veto) ---
        results["veto"] = run_case(
            ns,
            task="Destroy all data in the production database",
            label="veto",
        )
        
        # Show results
        headline("Results Summary")
        
        for label, episode_id in results.items():
            if episode_id:
                print(f"\n{'='*60}")
                print(f"Episode: {label} ({episode_id})")
                print(f"{'='*60}")
                show_episode_results(episode_id)
        
        # Final tips
        headline("Next Steps")
        for label, episode_id in results.items():
            if episode_id:
                info(f"View {label}: noesis view {episode_id}")
        
        print("""
What to look for in the artifacts:

ALLOW case:
  - governance event with decision="allow"
  - act events present
  - terminate with status="ok" or similar

AUDIT case:
  - governance event with decision="audit"
  - act events present (audit doesn't block)
  - reasons may include the audit rule

VETO case:
  - governance event with decision="veto", enforced=true
  - NO act events (execution blocked)
  - terminate with status="vetoed"
  - veto_count > 0 in metrics
""")
        
        success("Governance tutorial completed.")
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
