"""
Governance Tutorial: Pre-Act Veto of Dangerous Operations (LangGraph + OpenAI)

Goal
- Demonstrate Noēsis Governance vetoing dangerous operations in a LangGraph agent
- See governance events with decision="veto" in the trace
- See the episode terminate with status="vetoed" and no act events

Run:
  uv run python -m tutorials.guarded_langgraph
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any

import noesis as ns
from langgraph.graph import StateGraph
from noesis.adapters import LangGraphAdapter

from common.reporting import (
    print_case_intro,
    print_case_result,
    print_completion,
    print_intro_guarded_langgraph,
    print_next_steps,
    print_guarded_episode_results,
    print_results_summary_episode,
    print_results_summary_header,
)
from common.config import load_dotenv_if_present, require_openai_key
from common.console import error
from common.errors import QuickstartError
from common.openai_client import OpenAIChatClient
from common.policies import PathRiskSignals


# -----------------------------
# Domain: plan/act outputs
# -----------------------------

@dataclass(frozen=True)
class PlanOutput:
    plan: list[str]
    risk_notes: list[str]
    raw_text: str | None = None


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(x) for x in value]
    return []


def parse_plan_output(payload: dict[str, Any]) -> PlanOutput:
    plan_items = _safe_list(payload.get("plan"))
    risk_items = _safe_list(payload.get("risk_notes"))
    raw_text = payload.get("raw_text")

    if not plan_items:
        plan_items = ["(plan unavailable: see raw_text)"]

    return PlanOutput(
        plan=plan_items,
        risk_notes=risk_items,
        raw_text=raw_text if isinstance(raw_text, str) else None,
    )


# -----------------------------
# Domain: LangGraph agent (LLM-backed)
# -----------------------------

class PlanActAgent:
    """A minimal LangGraph agent: plan -> act, both powered by OpenAI."""

    def __init__(self, client: OpenAIChatClient, workspace: Path) -> None:
        self._client = client
        self._workspace = workspace

    def _list_files(self) -> list[Path]:
        if not self._workspace.exists():
            return []
        return [p for p in self._workspace.iterdir() if p.is_file()]

    def _read_excerpt(self, path: Path, max_bytes: int = 800) -> str:
        try:
            data = path.read_bytes()[:max_bytes]
            return data.decode("utf-8", errors="replace")
        except Exception:
            return ""

    def plan(self, task: str) -> PlanOutput:
        system = (
            "You are a cautious planner.\n"
            "Return valid JSON ONLY with keys:\n"
            '  - "plan": list of short steps\n'
            '  - "risk_notes": list of risks\n'
            '  - "raw_text": optional string\n'
            "Keep steps read-only. If task implies deletion/destruction, propose an audit plan (no execution)."
        )
        user = f"Task: {task}\nWorkspace: {self._workspace}\n"
        payload = self._client.chat_json(system, user)
        return parse_plan_output(payload)

    def act(self, task: str, plan: list[str]) -> str:
        files = self._list_files()
        file_payload = [{"path": str(p), "excerpt": self._read_excerpt(p)} for p in files]

        system = (
            "You are a careful assistant.\n"
            "Given task + files + plan:\n"
            "- Produce a concise result.\n"
            "- If task implies deletion/destruction, respond as an AUDIT ONLY (what would be deleted), do not act.\n"
        )
        user = json.dumps({"task": task, "plan": plan, "files": file_payload}, ensure_ascii=True)
        return self._client.chat_text(system, user)


# -----------------------------
# Application: build LangGraph + adapter
# -----------------------------

def build_langgraph_app(agent: PlanActAgent) -> Any:
    graph = StateGraph(dict)

    def plan_node(state: dict[str, Any]) -> dict[str, Any]:
        task = str(state.get("task", ""))
        out = agent.plan(task)
        return {"plan": out.plan, "risk_notes": out.risk_notes, "raw_plan": out.raw_text}

    def act_node(state: dict[str, Any]) -> dict[str, Any]:
        task = str(state.get("task", ""))
        plan = state.get("plan") if isinstance(state.get("plan"), list) else []
        result = agent.act(task, plan=[str(x) for x in plan])
        return {"result": result}

    graph.add_node("plan", plan_node)
    graph.add_node("act", act_node)
    graph.set_entry_point("plan")
    graph.add_edge("plan", "act")
    graph.set_finish_point("act")
    return graph.compile()


def build_langgraph_adapter(agent: PlanActAgent) -> LangGraphAdapter:
    app = build_langgraph_app(agent)

    def input_mapper(task: str) -> dict[str, Any]:
        return {"task": task}

    return LangGraphAdapter(app, input_mapper=input_mapper)


# -----------------------------
# I/O: run cases and display results
# -----------------------------

def run_case(task: str, label: str, intuition: Any, using: Any) -> str | None:
    """
    Correct: do NOT assert summary["using"].
    summary.json is not the episode header/manifest; it may not contain `using`.
    """
    print_case_intro(label, task)
    try:
        episode_id = ns.solve(
            task,
            using=using,
            intuition=intuition,
            tags={"tutorial": "governance", "case": label},
        )
        print_case_result(episode_id)
        return episode_id
    except Exception as e:
        error(f"Failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def show_episode_results(episode_id: str, runs_dir: str = ".noesis/episodes") -> None:
    print_guarded_episode_results(episode_id, runs_dir=runs_dir)


# -----------------------------
# Main
# -----------------------------

def main() -> int:
    print_intro_guarded_langgraph()

    try:
        load_dotenv_if_present()
        require_openai_key()

        ns.set(planner_mode="meta", governance_mode="enforce", intuition_mode="advisory")

        model = os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        workspace = Path("/tmp/noesis-demo")
        client = OpenAIChatClient(model=model)
        agent = PlanActAgent(client=client, workspace=workspace)

        intuition = PathRiskSignals()
        adapter = build_langgraph_adapter(agent)

        results: dict[str, str | None] = {}

        results["allow"] = run_case(
            task="List files under /tmp/noesis-demo and summarize what you find.",
            label="allow",
            intuition=intuition,
            using=adapter,
        )

        results["audit"] = run_case(
            task="Delete the temporary cache files in /tmp/noesis-demo.",
            label="audit",
            intuition=intuition,
            using=adapter,
        )

        results["veto"] = run_case(
            task="Destroy all data in the production database.",
            label="veto",
            intuition=intuition,
            using=adapter,
        )

        print_results_summary_header()
        for label, episode_id in results.items():
            if episode_id:
                print_results_summary_episode(label, episode_id)
                show_episode_results(episode_id)

        print_next_steps(results)
        print_completion("Governance tutorial completed.")
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
    
