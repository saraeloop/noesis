"""
Deterministic projection helpers for the non-cognitive portions of state.json.

These helpers make the runtime's projection rules explicit for fields that are
persisted in state but are not primary cognitive events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(slots=True, frozen=True)
class StateProjection:
    """Trace-backed projection of persisted outcome metadata and artifact links."""

    status: str
    summary: str | None
    metrics: dict[str, Any]
    links: dict[str, str]

    def to_payload(self) -> dict[str, Any]:
        """Convert the projection into the runtime event payload shape."""
        return {
            "kind": "run.state_projection",
            "status": self.status,
            "outcomes": {
                "status": self.status,
                "summary": self.summary,
                "metrics": dict(self.metrics),
            },
            "links": dict(self.links),
        }


def derive_state_links(*, terminal: bool) -> dict[str, str]:
    """Return the canonical artifact links for the current lifecycle state."""
    links = {
        "events": "events.jsonl",
        "learn": "learn.jsonl",
    }
    if terminal:
        links["summary"] = "summary.json"
        links["manifest"] = "manifest.json"
    return links


def build_state_projection_payload(
    *,
    status: str,
    summary: str | None,
    metrics: Mapping[str, Any] | None,
    links: Mapping[str, str],
) -> dict[str, Any]:
    """Build the canonical runtime event payload for state projection evidence."""
    projection = StateProjection(
        status=status,
        summary=summary,
        metrics=dict(metrics or {}),
        links={str(key): str(value) for key, value in links.items()},
    )
    return projection.to_payload()


def project_state_projection(events: Sequence[Mapping[str, object]]) -> StateProjection | None:
    """Read the latest runtime state projection from the event stream."""
    for event in reversed(events):
        if event.get("phase") != "runtime" or event.get("event_type") != "run.state_projection":
            continue
        payload = event.get("payload")
        if not isinstance(payload, Mapping):
            return None
        outcomes = payload.get("outcomes")
        links = payload.get("links")
        if not isinstance(outcomes, Mapping) or not isinstance(links, Mapping):
            return None
        status = outcomes.get("status")
        if not isinstance(status, str):
            return None
        summary = outcomes.get("summary")
        metrics = outcomes.get("metrics")
        return StateProjection(
            status=status,
            summary=summary if isinstance(summary, str) else None,
            metrics=dict(metrics) if isinstance(metrics, Mapping) else {},
            links={
                str(key): str(value)
                for key, value in links.items()
                if isinstance(key, str) and isinstance(value, str)
            },
        )
    return None
