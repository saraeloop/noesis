from __future__ import annotations

from typing import Any

import noesis as ns


class PathRiskSignals(ns.DirectedIntuition):
    """Advisory-only intuition signals for protected paths/resources."""

    __version__ = "0.1"

    def advise(self, state: dict[str, Any]) -> "ns.IntuitionEvent | None":
        task = (state.get("task") or "").lower()
        signals: list[str] = []

        if "/prod-data" in task:
            signals.append("/prod-data")
        if "/etc" in task:
            signals.append("/etc")
        if "~/.ssh" in task:
            signals.append("~/.ssh")
        if "prod database" in task or "production database" in task:
            signals.append("prod database")

        if not signals:
            return None

        return self.hint(
            advice="Potentially protected resource mentioned: " + ", ".join(signals),
            target="plan",
            rationale="Advisory-only signal for high-risk paths. Governance remains enforcement.",
        )
