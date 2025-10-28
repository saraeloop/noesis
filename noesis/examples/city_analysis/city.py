"""
Domain-specific intuition policy for city comparison.
"""

from __future__ import annotations
import noesis as ns  # top-level ergonomic imports

class CityIntuition(ns.Intuition):
    """
    Simple domain heuristic:
    - When comparing cities, nudge the agent to normalize numerical metrics
      and reason about tradeoffs between economy and culture.
    """
    def advise(self, ctx) -> ns.IntuitionEvent | None:
        task = (ctx.get("task") or "").lower()
        if "compare" in task and any(k in task for k in ("population", "gdp")):
            return ns.IntuitionEvent(
                kind="hint",
                advice=(
                    "Normalize population and GDP per capita before comparing; "
                    "explicitly note orders of magnitude and tradeoffs "
                    "(economy vs culture)."
                ),
                confidence=0.7,
                applied=False,
                rationale="Fairness heuristic for apples-to-apples comparisons.",
                evidence_ids=[],
            )
        return None