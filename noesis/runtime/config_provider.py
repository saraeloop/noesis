"""Shared configuration provider wiring ConfigPort to the runtime."""

from __future__ import annotations

from threading import RLock
from typing import Optional

from noesis.interfaces.config import ConfigPort, ConfigSnapshot
from noesis.infrastructure.config import EnvTomlConfig

__all__ = ["get_config_port", "set_config_port", "get_config_snapshot"]

_LOCK = RLock()
_PORT: Optional[ConfigPort] = None


def get_config_port() -> ConfigPort:
    """Return the active ConfigPort, instantiating a default if needed."""
    global _PORT
    with _LOCK:
        if _PORT is None:
            _PORT = EnvTomlConfig()
        return _PORT


def set_config_port(port: ConfigPort) -> None:
    """Override the active ConfigPort (primarily for tests/wiring)."""
    global _PORT
    with _LOCK:
        _PORT = port


def get_config_snapshot() -> ConfigSnapshot:
    """Convenience helper returning the current configuration snapshot."""
    return get_config_port().get()
