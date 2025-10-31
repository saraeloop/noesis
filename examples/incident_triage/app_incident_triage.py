"""
Simplified incident triage workflow used by the Gradio/Streamlit demos.

It intentionally keeps the logic deterministic so anyone can run the
example without external API keys. Each node carries TODO comments that
point to the real systems you would integrate in production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class IncidentState:
    """Lightweight state object shuttled between the demo nodes."""

    incident: str
    signals: List[str] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    approvals: List[Dict[str, Any]] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    severity: str = "unknown"


# --- Node implementations ----------------------------------------------------

def _detector(state: IncidentState) -> None:
    """
    Inspect the incoming incident description and emit initial signals.

    TODO: Replace keyword checks with actual observability queries
    (Prometheus, Datadog, Grafana Cloud, etc.).
    """
    text = state.incident.lower()
    if "5xx" in text or "outage" in text:
        state.severity = "critical"
        state.signals.append("detector:service_outage")
    elif "latency" in text or "slow" in text:
        state.severity = "high"
        state.signals.append("detector:latency_spike")
    else:
        state.severity = "medium"
        state.signals.append("detector:generic_event")


def _responder(state: IncidentState) -> None:
    """
    Suggest a next action based on heuristics.

    TODO: Call into LangGraph/LangChain to generate plan steps using
    runbook context, recent deploy diffs, and live metrics.
    """
    text = state.incident.lower()
    step: Dict[str, Any]
    if "purge" in text and "cache" in text:
        step = {"title": "Purge edge cache", "action": "purge_cache", "risk": "medium"}
    elif "rollback" in text or "roll back" in text:
        step = {
            "title": "Rollback latest deploy",
            "action": "trigger_rollback",
            "risk": "high",
        }
    elif "scale" in text:
        step = {"title": "Scale service", "action": "auto_scale", "risk": "medium"}
    else:
        step = {"title": "Triage playbook", "action": "triage_playbook", "risk": "low"}

    step["status"] = "proposed"
    state.actions.append(step)
    state.notes.append(f"Responder selected {step['action']} (severity={state.severity})")


def _reviewer(state: IncidentState, *, require_approval: bool = False) -> None:
    """
    Simulate the human-in-the-loop approval step.

    TODO: Drive this via Slack/Jira/ServiceNow approvals instead of a
    deterministic rule.
    """
    latest = state.actions[-1] if state.actions else {}
    requires_scope = latest.get("risk") == "high" and "canary" not in state.incident.lower()
    if require_approval:
        requires_scope = True

    approval = {
        "action": latest.get("action"),
        "status": "awaiting_approval" if requires_scope else "approved",
    }
    state.approvals.append(approval)
    state.notes.append(f"Reviewer status: {approval['status']}")

    if requires_scope:
        latest["status"] = "blocked_pending_approval"
        state.notes.append("reflect: human_ok pending")
    else:
        latest["status"] = "approved"
        state.notes.append("reflect: human_ok")


# --- Adapter callable --------------------------------------------------------

def incident_graph(task: str, *, tags: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Core callable consumed by ``noesis.run_using``.

    Noēsis adapters can be any callable that accepts a task and returns
    structured data; this keeps the demo approachable while mirroring
    how you would wrap a LangGraph workflow.
    """
    tags = tags or {}
    state = IncidentState(incident=task)
    _detector(state)
    _responder(state)
    _reviewer(state, require_approval=bool(tags.get("require_approval")))

    return {
        "severity": state.severity,
        "signals": state.signals,
        "actions": state.actions,
        "approvals": state.approvals,
        "notes": state.notes,
    }
