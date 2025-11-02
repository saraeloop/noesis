"""
Public runtime context utilities.

This facade exposes the supported context/config entry points so callers do
not need to import from `noesis.runtime.config_provider` directly.
"""

from __future__ import annotations

from .runtime.config_provider import (
    RuntimeContext,
    create_runtime_context,
    get_context,
    set_context,
    get_config_port,
    set_config_port,
    get_config_snapshot,
)

__all__ = [
    "RuntimeContext",
    "create_runtime_context",
    "get_context",
    "set_context",
    "get_config_port",
    "set_config_port",
    "get_config_snapshot",
]
