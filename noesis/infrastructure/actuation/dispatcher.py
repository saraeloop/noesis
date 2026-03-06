"""Infrastructure dispatcher for governed actuation executors."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from noesis.runtime.actuation_registry import get_actuation_registry

PayloadDispatcher = Callable[[Mapping[str, Any]], Any]
Executor = Callable[..., Any]


def resolve_executor(kind: str) -> PayloadDispatcher:
    """Resolve a configured actuation executor and normalize its payload call shape."""

    registry = get_actuation_registry()
    raw_executor = _resolve_registry_executor(kind, registry)
    return lambda payload: invoke_executor(raw_executor, payload)


def invoke_executor(executor: Executor, payload: Mapping[str, Any]) -> Any:
    """Invoke an executor with keyword-first fallback to payload-only dispatch."""

    try:
        return executor(**dict(payload))
    except TypeError:
        return executor(payload)


def _resolve_registry_executor(kind: str, registry: Any) -> Executor:
    if kind == "shell":
        if registry.shell_executor is None:
            raise ValueError("shell executor is not configured; call ns.set(shell_executor=...)")
        return registry.shell_executor
    if kind == "adapter":
        if registry.adapter_executor is None:
            raise ValueError("adapter executor is not configured; call ns.set(adapter_executor=...)")
        return registry.adapter_executor
    raise ValueError(f"unsupported action kind: {kind!r}")


__all__ = ["resolve_executor", "invoke_executor"]
