from __future__ import annotations

from importlib import import_module

from noesis.context import RuntimeContext


def require_actuation_port(context: RuntimeContext):
    """Return the configured actuation port or a default implementation."""
    try:
        return context.require("actuation", "actuation/1.0")
    except Exception:
        default_actuation = import_module("noesis.infrastructure.actuation.default_actuation")
        return default_actuation.DefaultActuationPort()


__all__ = ["require_actuation_port"]
