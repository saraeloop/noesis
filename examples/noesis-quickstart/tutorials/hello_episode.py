from __future__ import annotations

from pathlib import Path

from common.console import headline, info, success, warn, error
from common.config import load_dotenv_if_present, require_openai_key, import_noesis
from common.episode_io import episode_dir, read_events_jsonl, read_summary_json, summarize_timeline
from common.errors import QuickstartError


DEMO_ROOT = Path("/tmp/noesis-demo")
DEMO_README = """Noesis Demo Workspace
======================

This scratch space exists so the tutorial has real files to point at.
- The agent should summarize these files.
- The summary should call out the TODO items.
"""
DEMO_TODO = """TODO
- Add a safety policy for protected paths (/prod-data, /etc, ~/.ssh).
- Write a short project summary for new contributors.
"""


def write_demo_files(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    readme_path = root / "readme.txt"
    todo_path = root / "todo.txt"
    readme_path.write_text(DEMO_README, encoding="utf-8")
    todo_path.write_text(DEMO_TODO, encoding="utf-8")
    return {"readme": readme_path, "todo": todo_path}


def timeline_lines(events: list[dict], limit: int = 10) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = []
    for verb, status in summarize_timeline(events, limit=limit):
        if verb == "memory" and status in {"port_missing", "missing", "unavailable"}:
            status = "optional (port missing)"
        lines.append((verb, status))
    return lines


def event_excerpt(events: list[dict], limit: int = 3) -> list[str]:
    excerpt = []
    for event in events[:limit]:
        phase = event.get("phase", "unknown")
        event_id = event.get("id", "unknown")
        caused_by = event.get("caused_by", "none")
        excerpt.append(f"phase={phase} id={event_id} caused_by={caused_by}")
    return excerpt


def causal_chain(events: list[dict]) -> list[str]:
    chain = []
    phase_map: dict[str, dict] = {}
    for event in events:
        phase = event.get("phase")
        if phase and phase not in phase_map:
            phase_map[phase] = event

    chain_order = [
        ("intent (observe)", "observe"),
        ("plan", "plan"),
        ("act", "act"),
        ("terminate", "terminate"),
    ]
    for label, phase in chain_order:
        event = phase_map.get(phase)
        if not event:
            chain.append(f"{label}: (missing)")
            continue
        event_id = event.get("id", "unknown")
        caused_by = event.get("caused_by", "none")
        chain.append(f"{label}: id={event_id} caused_by={caused_by}")
    return chain


def summary_excerpt(summary: dict) -> list[str]:
    lines = []
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    lines.append(f"metrics.success: {metrics.get('success')}")
    return lines


def main() -> int:
    headline("Hello Episode — See Your Agent Think")

    try:
        ns = import_noesis()

        demo_files = write_demo_files(DEMO_ROOT)
        info(f"Scratch workspace: {DEMO_ROOT}")

        task = (
            f"Summarize the contents of {demo_files['readme']} and {demo_files['todo']}. "
            "Then propose 1-2 concrete next actions."
        )
        info(f"Task: {task}")

        # Noesis API path 
        episode_id = ns.run(task, intuition=True)
        success(f"Episode ID: {episode_id}")

        # Your repo’s README says runs are under ./runs by default.
        # If you want a fixed label, set it explicitly:
        # ns.set(runs_dir="./runs/demo")

        runs_dir = "runs"  # repo-root relative
        ep_dir = episode_dir(runs_dir, episode_id)
        success(f"Episode folder: {ep_dir}")

        events = read_events_jsonl(runs_dir=runs_dir, episode_id=episode_id, limit=30)
        summary = read_summary_json(runs_dir=runs_dir, episode_id=episode_id)

        headline("Timeline (first 10 phases)")
        for verb, status in timeline_lines(events, limit=10):
            print(f"[{verb:<12}] {status}")

        headline("What to inspect")
        print(f"events.jsonl: {ep_dir / 'events.jsonl'}")
        for line in event_excerpt(events, limit=3):
            print(f"  {line}")
        print("causal chain: intent → plan → act → terminate")
        for line in causal_chain(events):
            print(f"  {line}")
        print(f"summary.json: {ep_dir / 'summary.json'}")
        for line in summary_excerpt(summary):
            print(f"  {line}")

        if any(e.get("phase") == "memory" for e in events):
            info("Memory is optional in this tutorial; missing ports are not errors.")

        info(f"Tip: run `noesis view {episode_id}` for the full humanized timeline.")
        success("Hello Episode completed.")
        return 0

    except QuickstartError as e:
        error(str(e))
        return 2
    except Exception as e:
        error(f"Unexpected failure: {e}")
        warn("If artifacts weren’t found, confirm where Noēsis is writing runs (runs_dir + label).")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
