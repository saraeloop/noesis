"""Adapter-backed actuator for running callable/graph executions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence
import inspect

from noesis.domain.planner.interfaces import ActuationResult, Actuator, EventBus
from noesis.domain.state import NoesisState

EXCERPT_IN_LEN: int = 120
EXCERPT_OUT_LEN: int = 400


def _resolve_input_mapper(graph: Any) -> Optional[Callable[[str], Any]]:
    mapper = getattr(graph, "__noesis_input_mapper__", None)
    return mapper if callable(mapper) else None


def _invoke_graph(graph: Any, payload: Any) -> Any:
    if hasattr(graph, "invoke"):
        return graph.invoke(payload)
    if hasattr(graph, "run"):
        return graph.run(payload)
    if callable(graph):
        return graph(payload)
    raise TypeError("object is neither runnable nor callable")


@dataclass(slots=True)
class AdapterActuator(Actuator):
    """Executes an external graph/callable while keeping governance in the runner."""

    graph: Any
    tool_label: str
    input_mapper: Optional[Callable[[str], Any]] = None

    def __post_init__(self) -> None:
        if self.input_mapper is None:
            self.input_mapper = _resolve_input_mapper(self.graph)

    def execute(
        self,
        *,
        plan: Sequence,
        request: "EpisodeRequest",
        state: NoesisState,
        event_bus: EventBus,
    ) -> ActuationResult:
        input_text = request.goal
        input_excerpt = str(input_text)[:EXCERPT_IN_LEN]
        payload = self.input_mapper(input_text) if self.input_mapper else input_text

        summary: str | None = None
        reasons: list[str] = []
        success = True
        status = "ok"
        try:
            result = _invoke_graph(self.graph, payload)
            summary = str(result)[:EXCERPT_OUT_LEN]
            reasons.append("adapter_ok")
        except Exception as exc:  # noqa: BLE001
            status = "error"
            success = False
            summary = str(exc)
            reasons.append("adapter_error")

        action = state.record_action(
            kind="adapter",
            tool=self.tool_label,
            input_excerpt=input_excerpt,
            result_status="ok" if success else "error",
            step_id=plan[-1].id if plan else None,
        )
        event_bus.emit_action(action)

        return ActuationResult(
            status=status,
            summary=summary,
            metrics={"success": 1.0 if success else 0.0},
            reasons=reasons,
            success=success,
        )


async def _invoke_graph_async(graph: Any, payload: Any) -> Any:
    if hasattr(graph, "invoke"):
        result = graph.invoke(payload)
    elif hasattr(graph, "run"):
        result = graph.run(payload)
    elif callable(graph):
        result = graph(payload)
    else:
        raise TypeError("object is neither runnable nor callable")
    if inspect.isawaitable(result):
        return await result
    return result


@dataclass(slots=True)
class AsyncAdapterActuator(Actuator):
    """Executes an external graph/callable with async-aware invocation."""

    graph: Any
    tool_label: str
    input_mapper: Optional[Callable[[str], Any]] = None

    def __post_init__(self) -> None:
        if self.input_mapper is None:
            self.input_mapper = _resolve_input_mapper(self.graph)

    async def execute(
        self,
        *,
        plan: Sequence,
        request: "EpisodeRequest",
        state: NoesisState,
        event_bus: EventBus,
    ) -> ActuationResult:
        input_text = request.goal
        input_excerpt = str(input_text)[:EXCERPT_IN_LEN]
        payload = self.input_mapper(input_text) if self.input_mapper else input_text

        summary: str | None = None
        reasons: list[str] = []
        success = True
        status = "ok"
        try:
            result = await _invoke_graph_async(self.graph, payload)
            summary = str(result)[:EXCERPT_OUT_LEN]
            reasons.append("adapter_ok")
        except Exception as exc:  # noqa: BLE001
            status = "error"
            success = False
            summary = str(exc)
            reasons.append("adapter_error")

        action = state.record_action(
            kind="adapter",
            tool=self.tool_label,
            input_excerpt=input_excerpt,
            result_status="ok" if success else "error",
            step_id=plan[-1].id if plan else None,
        )
        event_bus.emit_action(action)

        return ActuationResult(
            status=status,
            summary=summary,
            metrics={"success": 1.0 if success else 0.0},
            reasons=reasons,
            success=success,
        )
