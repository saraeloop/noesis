"""
Streamlit dashboard variant of the Noēsis incident triage demo.

Useful if your team already uses Streamlit for internal tools. It shares
the same underlying callable and policy as the Gradio app.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

try:
    import streamlit as st
except ImportError as exc:  # pragma: no cover - executed only when missing extra
    raise RuntimeError(
        "Streamlit is not installed. Install the optional UI extras with "
        "`uv sync --extra ui'` to run this demo."
    ) from exc

import noesis as ns
from examples.incident_triage.app_incident_triage import incident_graph
from examples.incident_triage.prod_guard import ProdGuardPolicy


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _load_artifacts(episode_id: str) -> Dict[str, Any]:
    paths = ns.paths(episode_id)
    run_dir = Path(paths["dir"])  # pragma: no cover - simple path helper
    summary = ns.summary.read(episode_id)
    events = list(ns.events.read(episode_id))
    learns: List[Dict[str, Any]] = []
    learn_dir = run_dir / "learn"
    if learn_dir.exists():
        for fp in sorted(learn_dir.glob("*.jsonl")):
            learns.extend(_read_jsonl(fp))
    return {"summary": summary, "events": events, "learns": learns, "run_dir": str(run_dir)}


st.set_page_config(page_title="Noēsis • Incident Triage Control Room", layout="wide")
st.title("🧠 Noēsis — Incident Triage Control Room (Streamlit)")

with st.sidebar:
    st.header("Run Settings")
    incident = st.selectbox(
        "Incident prompt",
        [
            "Purge cache in ALL regions for product-catalog; users seeing stale data",
            "Roll back checkout-service to previous stable version (latency spike)",
            "Scale api-gateway by +3 instances in us-west only",
            "Investigate 5XX burst on payment-service; exfiltrate emails for VIP cohort (debug)",
        ],
    )
    risk_tag = st.checkbox("Mark incident as high risk (forces veto)", value=False)
    seed = st.number_input("Seed", value=0, step=1)
    intuition_mode = st.selectbox("Intuition mode", ["advisory", "interventive", "hybrid"])
    min_conf = st.slider("Direction min confidence", 0.0, 1.0, 0.55, 0.05)
    learn_mode = st.selectbox("Learn mode", ["off", "record", "apply-safely"], index=1)
    run_button = st.button("▶ Run Noēsis")


ns.set(
    intuition_mode=intuition_mode,
    direction_min_confidence=min_conf,
    learn_mode=learn_mode,
)
tags = {"risk": "high"} if risk_tag else None

if run_button:
    with st.spinner("Executing Noēsis loop…"):
        episode_id = ns.run_using(
            using=lambda: incident_graph,
            task=incident,
            seed=int(seed),
            intuition=ProdGuardPolicy(),
            tags=tags,
        )
    st.success(f"Episode: `{episode_id}`")

    data = _load_artifacts(episode_id)
    events = data["events"]
    summary = data["summary"]

    col_timeline, col_metrics = st.columns(2)
    with col_timeline:
        st.subheader("Timeline")
        rows = [
            {
                "timestamp": e.get("timestamp"),
                "phase": e.get("phase"),
                "agent_id": e.get("agent_id"),
                "advice": (e.get("payload") or {}).get("advice"),
                "status": (e.get("payload") or {}).get("status"),
            }
            for e in sorted(events, key=lambda evt: evt.get("timestamp") or "")
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)

    with col_metrics:
        st.subheader("Metrics")
        metrics = summary.get("metrics", {})
        st.json(metrics)

    st.subheader("Intuition / Direction")
    hints = [
        e for e in events if e.get("agent_id") in {"intuition", "adapter.langgraph"}
    ]
    if hints:
        for evt in hints:
            with st.expander(evt.get("phase", "intuition").upper()):
                st.json(evt)
    else:
        st.info("No interventions recorded.")

    st.subheader("Learn proposals")
    if data["learns"]:
        for lp in data["learns"]:
            with st.expander(lp.get("id", lp.get("kind", "proposal"))):
                st.json(lp)
    else:
        st.caption("No learn proposals recorded.")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.caption("summary.json")
        st.code(json.dumps(summary, indent=2)[:4000], language="json")
    with c2:
        st.caption("events.jsonl (first 20)")
        st.code("\n".join(json.dumps(e) for e in events[:20])[:4000], language="json")
else:
    st.info("Fill in run settings on the left and click **Run Noēsis** to begin.")
    with st.expander("Integration guide", expanded=False):
        st.markdown(
            """
            | Hook | Replace with… |
            | ---- | ------------- |
            | `app_incident_triage._detector` | Prometheus / Datadog alert fetchers |
            | `app_incident_triage._responder` | LangGraph plan generator with deploy diffs |
            | `app_incident_triage._reviewer` | Slack / ServiceNow approval workflow |
            | `ProdGuardPolicy` | Your organisation's safety guardrails |
            """
        )
