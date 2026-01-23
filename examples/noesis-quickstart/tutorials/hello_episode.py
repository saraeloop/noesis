from __future__ import annotations

from pathlib import Path
import argparse
import os

from common.console import headline, info, success, warn, error
from common.config import import_noesis, load_dotenv_if_present, require_openai_key
from common.episode_io import episode_dir, read_events_jsonl, read_summary_json
from common.errors import QuickstartError
from common.openai_client import OpenAIChatClient


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


def causal_chain(events: list[dict]) -> list[str]:
    chain = []
    phase_map: dict[str, dict] = {}
    for event in events:
        phase = event.get("phase")
        if phase and phase not in phase_map:
            phase_map[phase] = event

    chain_order = [
        ("observe", "observe"),
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hello Episode tutorial (LLM required).")
    return parser.parse_args()


def main() -> int:
    _parse_args()
    headline("Hello Episode — See Your Agent Think")

    try:
        ns = import_noesis()
        load_dotenv_if_present()
        require_openai_key()

        model = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        client = OpenAIChatClient(model=model)

        def summarize_with_llm(task: str) -> str:
            readme = (DEMO_ROOT / "readme.txt").read_text(encoding="utf-8").strip()
            todo = (DEMO_ROOT / "todo.txt").read_text(encoding="utf-8").strip()
            system = (
                "You summarize two short files and propose 1–2 next actions. "
                "Keep it concise."
            )
            user = (
                f"Task: {task}\n\n"
                f"readme.txt:\n{readme}\n\n"
                f"todo.txt:\n{todo}\n"
            )
            summary = client.chat_text(system, user)
            (DEMO_ROOT / "summary.txt").write_text(summary.strip() + "\n", encoding="utf-8")
            return summary

        headline("WHAT YOU GET")
        print("- A model-backed episode with an auditable evidence bundle")
        print("- Verification assertions tied to a real workspace snapshot")
        print("- A sealed episode (final.json + manifest.json)")

        headline("HOW TO RUN")
        print("- OPENAI_API_KEY must be set in your environment")
        print("- uv run python -m tutorials.hello_episode")

        demo_files = write_demo_files(DEMO_ROOT)
        info(f"Scratch workspace: {DEMO_ROOT}")

        task = (
            f"Summarize the contents of {demo_files['readme']} and {demo_files['todo']}. "
            "Then propose 1-2 concrete next actions. "
            "Write the summary to summary.txt in the workspace."
        )
        info(f"Task: {task}")

        # Use a model-backed adapter + verification to demonstrate real assertions.
        verify = [
            ns.file_exists("readme.txt"),
            ns.file_exists("todo.txt"),
            ns.file_exists("summary.txt"),
            ns.file_contains("todo.txt", "TODO"),
        ]
        episode_id = ns.solve(
            task,
            using=summarize_with_llm,
            intuition=True,
            workspace=str(DEMO_ROOT),
            verify=verify,
        )
        success(f"Episode ID: {episode_id}")

        # Use the configured runs_dir to locate artifacts.
        config = ns.get()
        runs_dir = str(config.get("runs_dir", ".noesis/episodes"))
        ep_dir = episode_dir(runs_dir, episode_id)
        success(f"Episode folder: {ep_dir}")

        events = read_events_jsonl(runs_dir=runs_dir, episode_id=episode_id, limit=30)
        summary = read_summary_json(runs_dir=runs_dir, episode_id=episode_id)

        metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
        verification = summary.get("verification") if isinstance(summary.get("verification"), dict) else {}
        assertions = verification.get("assertions") if isinstance(verification.get("assertions"), list) else []

        headline("WHERE TO LOOK")
        print(f"- events.jsonl: {ep_dir / 'events.jsonl'} (phase + caused_by)")
        print(f"- summary.json: {ep_dir / 'summary.json'} (metrics.success, verification.assertions)")
        print(f"- final.json: {ep_dir / 'final.json'} (sealed outcome)")
        print(f"- manifest.json: {ep_dir / 'manifest.json'} (hash ledger)")

        headline("WHAT IT MEANS")
        print(f"- metrics.success: {metrics.get('success')}")
        print(f"- verification.provided: {verification.get('provided')} (assertions: {len(assertions)})")
        print("- workspace diff should show summary.txt as added")
        print("- causal chain (observe → plan → act → terminate):")
        for line in causal_chain(events):
            print(f"  {line}")
        print(f"- sealed: {(ep_dir / 'final.json').exists()}")

        info(f"Tip: run `uv run noesis view {episode_id}` for the full humanized timeline.")
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
