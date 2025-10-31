"""
Safety-first intuition policy used by the incident triage demos.

The policy exemplifies how teams can codify production guardrails with
Noēsis. It performs three tiers of protection:

1. Vetoes destructive or data-exfiltration intents outright.
2. Intervenes to scope risky actions (e.g., canary-only, enforce approvals).
3. Provides gentle hints when everything already looks safe.

The logic is deliberately deterministic so the demo can run without LLM
dependencies. In a real deployment you could enrich the state snapshot
with runbook context, on-call schedules, or change windows to produce
even richer interventions.
"""

from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

import noesis as ns

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from noesis.intuition import IntuitionEvent
else:  # pragma: no cover - runtime fallback
    IntuitionEvent = Any

# Regex shortcuts that approximate common SRE red flags.
_EXFIL = re.compile(r"\b(exfiltrat(e|ion)|leak|dump|expose)\b", re.I)
_DESTRUCT = re.compile(r"\b(drop\s+db|delete\s+all|shutdown\s+cluster|wipe)\b", re.I)
_GLOBAL = re.compile(r"\b(all\s+regions?|global)\b", re.I)
_PII = re.compile(r"\b(email|ssn|token|apikey|api_key|password)\b", re.I)


class ProdGuardPolicy(ns.DirectedIntuition):
    """Apply production safety heuristics to the current Noēsis episode."""

    __version__ = "1.1"

    def advise(self, state: dict[str, Any]) -> "IntuitionEvent | None":
        task = (state.get("task") or "").strip()
        tags = state.get("tags") or {}
        text = task.lower()

        # 1) Hard vetoes – block immediately.
        if _EXFIL.search(text) or tags.get("risk") == "high":
            return self.veto(
                advice="Blocked: potential data exfiltration.",
                target="plan",
                rationale="Policy forbids PII export/exfiltration in production.",
            )
        if _DESTRUCT.search(text):
            return self.veto(
                advice="Blocked: destructive operation detected.",
                target="plan",
                rationale="Dangerous op requires privileged change window + approval.",
            )

        # 2) Scoped interventions – apply automatic safety patches.
        rationale: list[str] = []
        patch: dict[str, Any] = {}
        if _GLOBAL.search(text):
            patch["rewrite"] = re.sub(_GLOBAL, "region=us-west (canary-only)", task)
            rationale.append("Scoped action to canary region to reduce blast radius.")

        if patch:
            return self.intervene(
                advice="Applied safety scope.",
                patch=patch,
                target="input",
                rationale=" ".join(rationale) or "Scoped defaults.",
            )

        if _PII.search(text):
            return self.hint(
                advice="Mask PII in outputs and route logs to restricted sinks.",
                target="plan",
                rationale="PII detected in request. Ensure observability obeys policy.",
            )

        # 3) Soft nudge – keep responders thinking two steps ahead.
        return self.hint(
            advice="Prefer canary-first rollout and attach the relevant runbook link.",
            target="plan",
        )
