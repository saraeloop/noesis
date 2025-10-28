"""Guardrails flow to showcase the direction layer."""

from __future__ import annotations

from typing import Any, Dict


class _GuardrailsGraph:
    """Minimal LangGraph-compatible stub that expects dict input."""

    def __init__(self) -> None:
        # Ensures Noēsis maps string tasks into the dict structure we expect.
        self.__noesis_input_mapper__ = lambda task: {"task": task, "normalize": False, "risk": "medium"}

    def invoke(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        report: Dict[str, Any] = {
            "task": payload["task"],
            "normalize": payload.get("normalize", False),
            "risk": payload.get("risk", "unknown"),
        }
        if not report["normalize"]:
            report["status"] = "warn"
            report["message"] = "Data normalization was skipped."
        else:
            report["status"] = "ok"
            report["message"] = "Proceed with normalized data."

        if payload.get("risk") == "high":
            report["status"] = "block"
            report["message"] = "Risk too high; escalate to human."
        return report


def make() -> _GuardrailsGraph:
    return _GuardrailsGraph()
