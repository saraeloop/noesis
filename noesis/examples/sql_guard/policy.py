from __future__ import annotations

import re
from typing import Any

import noesis as ns
from noesis.intuition import IntuitionEvent

_DANGEROUS = re.compile(r"\b(drop\s+table|delete\s+from)\b", re.I)
_NO_WHERE_DELETE = re.compile(r"\bdelete\s+from\s+\w+\s*;$", re.I)
_PII_FIELDS = re.compile(r"\b(email|ssn|password|token|api_key)\b", re.I)


class SqlGuardPolicy(ns.DirectedIntuition):
    """Direction = (a) patch risky queries, (b) veto exfiltration."""

    __version__ = "1.0"

    def advise(self, state: dict[str, Any]) -> IntuitionEvent | None:
        task = (state.get("task") or "").strip()
        tags = state.get("tags") or {}
        text = task.lower()

        # Hard veto: explicit exfiltration intent
        if "exfiltrate" in text or tags.get("risk") == "high":
            return self.veto(
                advice="Blocked: potential data exfiltration.",
                target="plan",
                rationale="Policy forbids PII export / exfiltration.",
            )

        # If user passed a raw SQL (basic heuristic), patch it for safety
        is_sql = any(keyword in text for keyword in ("select", "insert", "update", "delete", "drop"))
        if is_sql:
            # veto DROP table (demo)
            if _DANGEROUS.search(text) and "drop" in text:
                return self.veto(
                    advice="Blocked: destructive DROP detected.",
                    target="plan",
                    rationale="Requires privileged mode & review.",
                )

            # require WHERE for DELETE; add LIMIT to SELECT if missing
            if _NO_WHERE_DELETE.search(task):
                return self.veto(
                    advice="Blocked: DELETE without WHERE.",
                    target="plan",
                    rationale="Prevent table-wide destructive operations.",
                )

            patch: dict[str, Any] = {}
            rationale_parts: list[str] = []

            if "select" in text and "limit" not in text:
                patch["rewrite"] = f"{task} LIMIT 100"
                rationale_parts.append("Added LIMIT 100 to bound result size.")

            if patch:
                return self.intervene(
                    advice="Applied safety patch to SQL.",
                    patch=patch,
                    target="input",
                    rationale=" ".join(rationale_parts) or "Safety defaults.",
                )

            # Otherwise just hint (non-blocking nudge)
            return self.hint(
                advice="Consider bounding result size and masking PII.",
                target="plan",
            )

        # Not SQL: no action
        return None
