"""Directed intuition policy used by the direction demo."""

from __future__ import annotations

from typing import Any

import noesis as ns


class GuardrailsPolicy(ns.DirectedIntuition):
    """Simple policy: normalize data and veto exfiltration tasks."""

    __version__ = "1.0"

    def advise(self, state: dict[str, Any]) -> ns.IntuitionEvent | None:
        task = (state.get("task") or "").lower()
        tags = state.get("tags") or {}

        if "exfiltrate" in task or tags.get("risk") == "high":
            return self.veto(
                advice="Reject task: potential data exfiltration detected.",
                rationale="Policy guardrail",
                target="plan",
            )

        if "normalize" not in task:
            return self.intervene(
                advice="Set normalize=True before running quality checks.",
                patch={"normalize": True},
                rationale="Ensure fair comparisons and stable downstream tools.",
                target="input",
            )

        return self.hint(
            advice="Document how normalization changes downstream metrics.",
            target="plan",
        )
