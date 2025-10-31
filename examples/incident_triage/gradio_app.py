"""
Gradio "control room" for the Noēsis incident triage demo.

The UI lets reviewers tweak safety knobs, execute an incident loop, and
inspect events/metrics/learn proposals produced by Noēsis. Everything is
deterministic so the experience works out-of-the-box; swap the TODO
sections in ``app_incident_triage`` with real integrations to go live.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

try:
    import gradio as gr
except ImportError as exc:  # pragma: no cover - executed only when missing extra
    raise RuntimeError(
        "Gradio is not installed. Install the optional UI extras with "
        "`uv pip install 'noesis[ui]'` to run this demo."
    ) from exc

import noesis as ns

from examples.incident_triage.app_incident_triage import incident_graph
from examples.incident_triage.prod_guard import ProdGuardPolicy

# Local sample run so the dashboard has meaningful content before the first run.
SAMPLE_RUN_DIR = Path(__file__).with_name("demo_run")


# Helpers                                                                     

def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _load_artifacts_from_dir(run_dir: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], str]:
    summary: Dict[str, Any] = {}
    events: List[Dict[str, Any]] = []
    learns: List[Dict[str, Any]] = []

    if (run_dir / "summary.json").exists():
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    if (run_dir / "events.jsonl").exists():
        events = _read_jsonl(run_dir / "events.jsonl")
    learn_dir = run_dir / "learn"
    if learn_dir.exists():
        for fp in sorted(learn_dir.glob("*.jsonl")):
            learns.extend(_read_jsonl(fp))

    return summary, events, learns, str(run_dir)


def _load_sample_artifacts() -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], str]:
    if SAMPLE_RUN_DIR.exists():
        return _load_artifacts_from_dir(SAMPLE_RUN_DIR)
    return {}, [], [], str(SAMPLE_RUN_DIR)


def _sorted_events(events: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(events, key=lambda e: e.get("timestamp") or "")


def _badge_for_event(event: Dict[str, Any]) -> str:
    phase = (event.get("phase") or "").lower()
    payload = event.get("payload") or {}
    if phase == "direction":
        if payload.get("status") == "blocked" or payload.get("kind") == "veto":
            return "🚫 VETO"
        if payload.get("applied"):
            return "🩹 PATCH"
    if phase == "intuition":
        return "💡 HINT"
    return ""


def _phase_options(events: Iterable[Dict[str, Any]]) -> List[str]:
    phases = { (evt.get("phase") or "").upper() for evt in events if evt.get("phase") }
    return sorted(phases) or ["START", "OBSERVE", "PLAN", "ACT", "REFLECT", "LEARN"]


def _agent_options(events: Iterable[Dict[str, Any]]) -> List[str]:
    agents = { evt.get("agent_id") or "system" for evt in events }
    return sorted(agents)


def _timeline_markdown(
    events: List[Dict[str, Any]],
    phases: Iterable[str] | None = None,
    agent: str | None = None,
) -> str:
    if not events:
        return "_No events captured for this run._"

    phase_set = {p.upper() for p in phases or [] if p}
    agent = (agent or "").strip()

    rows = [
        "| Time | Phase | Agent | Details |",
        "| ---- | ----- | ------ | ------- |",
    ]

    for evt in _sorted_events(events):
        phase = (evt.get("phase") or "").upper()
        agent_id = evt.get("agent_id") or "system"
        if phase_set and phase not in phase_set:
            continue
        if agent and agent != "All" and agent_id != agent:
            continue

        payload = evt.get("payload") or {}
        details = payload.get("advice") or payload.get("outcome") or payload.get("status") or ""
        badge = _badge_for_event(evt)
        phase_cell = phase if not badge else f"{phase} <span style='font-size:0.85em;'>({badge})</span>"
        rows.append(f"| {evt.get('timestamp', '—')} | {phase_cell} | `{agent_id}` | {details} |")

    if len(rows) == 2:
        return "_No events matched the selected filters._"
    return "\n".join(rows)


def _metric_summary(summary: Dict[str, Any]) -> str:
    if not summary:
        return "_No summary.json written (run aborted early)._"

    metrics = summary.get("metrics") or {}
    lines = [
        "| Metric | Value |",
        "| ------ | ----- |",
    ]

    def _add(key: str, fmt=lambda x: x) -> None:
        if key in metrics:
            lines.append(f"| `{key}` | {fmt(metrics[key])} |")

    _add("success")
    _add("steps")
    _add("plan_count")
    _add("act_count")
    _add("reflect_count")
    _add("veto_rate", fmt=lambda v: f"{v:.2f}")
    latencies = metrics.get("latencies") or {}
    if latencies:
        lines.append("| `latencies` | " + ", ".join(f"{k}={v}ms" for k, v in latencies.items()) + " |")

    learn = metrics.get("learn_proposals")
    if learn:
        lines.append(f"| `learn_proposals` | {len(learn)} recorded |")

    return "\n".join(lines)


def _intervention_summary(events: List[Dict[str, Any]]) -> str:
    hints = [
        evt
        for evt in events
        if evt.get("agent_id") in {"intuition", "adapter.langgraph"}
        and evt.get("phase") in {"intuition", "direction"}
    ]
    if not hints:
        return "_No hints or interventions recorded._"
    rows = []
    for evt in hints:
        payload = evt.get("payload") or {}
        rows.append(
            f"* **{evt.get('phase').upper()}** — {payload.get('advice','(no advice)')}  "
            f"_rationale: {payload.get('rationale','n/a')}_"
        )
    return "\n".join(rows)


def _load_run_artifacts(episode_id: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], str]:
    paths = ns.paths(episode_id)
    run_dir = Path(paths["dir"])
    summary = ns.summary(episode_id)
    events = ns.events(episode_id)
    learns: List[Dict[str, Any]] = []
    learn_dir = run_dir / "learn"
    if learn_dir.exists():
        for fp in sorted(learn_dir.glob("*.jsonl")):
            learns.extend(_read_jsonl(fp))
    return summary, list(events), learns, paths["dir"]


def _learn_badge(learns: List[Dict[str, Any]]) -> str:
    if not learns:
        return "Learn proposals: 0"
    pending = sum(1 for lp in learns if lp.get("status", "pending") not in {"applied", "accepted"})
    badge = f"Learn proposals: {len(learns)}"
    if pending:
        badge += f" (pending: {pending})"
    else:
        badge += " (all applied)"
    return badge


SAMPLE_SUMMARY, SAMPLE_EVENTS, SAMPLE_LEARNS, SAMPLE_PATH = _load_sample_artifacts()
SAMPLE_PHASES = _phase_options(SAMPLE_EVENTS)
SAMPLE_AGENTS = _agent_options(SAMPLE_EVENTS)


# Gradio callback                                                             

def run_demo(
    prompt: str,
    seed: int,
    intuition_mode: str,
    min_conf: float,
    learn_mode: str,
    risk_flag: bool,
    require_approval: bool,
) -> Tuple[
    List[Dict[str, Any]],
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    str,
    Dict[str, Any],
    Dict[str, Any],
    str,
    Dict[str, Any],
    Dict[str, Any],
]:
    ns.set(
        intuition_mode=intuition_mode,
        direction_min_confidence=min_conf,
        learn_mode=learn_mode,
    )
    tags: Dict[str, Any] = {}
    if risk_flag:
        tags["risk"] = "high"
    if require_approval:
        tags["require_approval"] = True

    episode_id = ns.run_using(
        using=lambda: incident_graph,
        task=prompt,
        seed=int(seed),
        intuition=ProdGuardPolicy(),
        tags=tags,
    )

    summary, events, learns, run_dir = _load_run_artifacts(episode_id)
    phases = _phase_options(events)
    agents = _agent_options(events)

    timeline = _timeline_markdown(events, phases, "All")
    learn_text = json.dumps(learns, indent=2) if learns else "_No learn proposals recorded._"
    summary_text = json.dumps(summary, indent=2) if summary else "_summary.json not found._"
    events_text = "\n".join(json.dumps(evt) for evt in events[:30]) or "_events.jsonl empty._"

    return (
        events,
        f"**Episode:** `{episode_id}`",
        f"_{_learn_badge(learns)}_",
        timeline,
        _metric_summary(summary),
        _intervention_summary(events),
        learn_text,
        summary_text,
        events_text,
        f"Artifacts written to `{run_dir}`",
        gr.update(choices=phases, value=phases),
        gr.update(choices=["All"] + agents, value="All"),
        str(run_dir),
    )


# UI builder                                                                  

def build_interface() -> gr.Blocks:
    with gr.Blocks(title="Noēsis Incident Triage") as demo:
        gr.Markdown(
            """
            # 🧠 Noēsis Incident Triage — Gradio Control Room
            Configure safety knobs, run a deterministic incident loop, and inspect the
            **Noēsis** artifacts (events, metrics, learn proposals) a production on-call
            team would use. Everything here runs without API keys; swap the TODO hooks in
            the source files for Prometheus/GitHub/Kubernetes to go live.
            """
        )

        with gr.Accordion("Where to plug in production systems", open=False):
            gr.Markdown(
                """
                | Location | Replace with… |
                | --- | --- |
                | `app_incident_triage._detector` | PromQL / Datadog / Grafana alerts |
                | `app_incident_triage._responder` | LangGraph plan generator with deploy diffs |
                | `app_incident_triage._reviewer` | Slack / Jira / ServiceNow approvals |
                | `ProdGuardPolicy` | Your own safety rules & patch heuristics |
                """
            )

        with gr.Row():
            with gr.Column(scale=1):
                prompt = gr.Textbox(
                    label="Incident prompt",
                    value="Purge cache in ALL regions for product-catalog; users seeing stale data",
                    lines=3,
                )
                risk_flag = gr.Checkbox(label="Mark as high risk (forces veto)", value=False)
                seed = gr.Number(label="Seed", value=0, precision=0)

            with gr.Column(scale=1):
                intuition_mode = gr.Dropdown(
                    ["advisory", "interventive", "hybrid"],
                    value="advisory",
                    label="Intuition mode",
                )
                min_conf = gr.Slider(
                    minimum=0.0,
                    maximum=1.0,
                    value=0.55,
                    step=0.05,
                    label="Direction min confidence",
                )
                learn_mode = gr.Dropdown(
                    ["off", "record", "apply-safely"],
                    value="record",
                    label="Learn mode",
                )
                require_approval = gr.Checkbox(
                    label="Require human approval (simulate longer path)",
                    value=False,
                )

        run_button = gr.Button("▶ Run Noēsis")
        learn_badge = gr.Markdown(f"_{_learn_badge(SAMPLE_LEARNS)}_", elem_id="learn-badge")

        with gr.Row():
            phase_filter = gr.CheckboxGroup(
                label="Phase filter",
                choices=SAMPLE_PHASES,
                value=SAMPLE_PHASES,
                interactive=True,
            )
            agent_filter = gr.Dropdown(
                label="Agent",
                choices=["All"] + SAMPLE_AGENTS,
                value="All",
                interactive=True,
            )

        with gr.Tabs():
            with gr.Tab("Timeline"):
                timeline_md = gr.Markdown(value=_timeline_markdown(SAMPLE_EVENTS, SAMPLE_PHASES, "All"))
            with gr.Tab("Metrics"):
                metrics_md = gr.Markdown(value=_metric_summary(SAMPLE_SUMMARY))
            with gr.Tab("Interventions"):
                interventions_md = gr.Markdown(value=_intervention_summary(SAMPLE_EVENTS))
            with gr.Tab("Learn proposals"):
                learn_box = gr.Textbox(
                    lines=10,
                    value=json.dumps(SAMPLE_LEARNS, indent=2) if SAMPLE_LEARNS else "_Run the demo to capture learning._",
                )
            with gr.Tab("summary.json"):
                summary_code = gr.Code(
                    language="json",
                    value=json.dumps(SAMPLE_SUMMARY, indent=2) if SAMPLE_SUMMARY else "{}",
                )
            with gr.Tab("events.jsonl"):
                events_code = gr.Code(
                    language="json",
                    value="\n".join(json.dumps(evt) for evt in SAMPLE_EVENTS[:30]) if SAMPLE_EVENTS else "[]",
                )

        episode_box = gr.Markdown(
            label="Episode",
            value="**Episode:** `demo_incident`" if SAMPLE_EVENTS else "_Episode ID will appear here._",
        )
        artifact_box = gr.Markdown(label="Artifacts path", value=f"Artifacts written to `{SAMPLE_PATH}`")

        run_dir_box = gr.Textbox(
            label="Run directory",
            value=SAMPLE_PATH,
            show_copy_button=True,
            interactive=False,
        )
        events_state = gr.State(SAMPLE_EVENTS)

        run_button.click(
            fn=run_demo,
            inputs=[prompt, seed, intuition_mode, min_conf, learn_mode, risk_flag, require_approval],
            outputs=[
                events_state,
                episode_box,
                learn_badge,
                timeline_md,
                metrics_md,
                interventions_md,
                learn_box,
                summary_code,
                events_code,
                artifact_box,
                phase_filter,
                agent_filter,
                run_dir_box,
            ],
        )

        def _refresh_timeline(events: List[Dict[str, Any]], phases: List[str], agent: str) -> str:
            return _timeline_markdown(events, phases, agent)

        phase_filter.change(
            fn=_refresh_timeline,
            inputs=[events_state, phase_filter, agent_filter],
            outputs=timeline_md,
        )
        agent_filter.change(
            fn=_refresh_timeline,
            inputs=[events_state, phase_filter, agent_filter],
            outputs=timeline_md,
        )

        gr.Markdown(
            """
            ### Want to embed this elsewhere?
            ```bash
            uv run python -m examples.incident_triage.gradio_app
            ```
            Swap in your production integrations and ship the same control room.
            """
        )

    return demo


# --------------------------------------------------------------------------- #

app = build_interface()

if __name__ == "__main__":
    app.launch()
