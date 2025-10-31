"""
Runtime observability adapters.

Bridges the domain event bus contract with the existing runtime event
emission helpers so the use cases remain framework-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from noesis.domain.planner.interfaces import EventBus
from noesis.domain.state import ActionRecord, PlanStep
from noesis.runtime._events import plan_event, act_event, reflect_event


@dataclass(slots=True)
class RuntimeEventBus(EventBus):
    """Concrete event bus that writes to the runtime JSONL logs."""

    run_dir: Path
    episode_id: str

    def emit_plan(self, *, steps: Sequence[PlanStep], rationale: str, source: str) -> None:
        labels = [f"{step.kind.value}:{step.description}" for step in steps]
        plan_event(self.run_dir, self.episode_id, steps=labels, rationale=rationale, source=source)

    def emit_action(self, action: ActionRecord) -> None:
        act_event(
            self.run_dir,
            self.episode_id,
            adapter=action.tool,
            input_excerpt=action.input_excerpt,
            outcome=action.result_status,
        )

    def emit_reflect(self, *, success: bool, reasons: list[str]) -> None:
        reflect_event(self.run_dir, self.episode_id, success=success, reasons=reasons or None)
