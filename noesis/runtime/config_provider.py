"""Shared runtime container that wires ConfigPort and other infrastructure."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, Optional

from noesis.interfaces.config import ConfigPort, ConfigSnapshot
from noesis.infrastructure.config import EnvTomlConfig

__all__ = [
    "RuntimeContainer",
    "create_runtime_container",
    "get_container",
    "set_container",
    "get_config_port",
    "set_config_port",
    "get_config_snapshot",
]

_LOCK = RLock()
_CONTAINER: Optional["RuntimeContainer"] = None


@dataclass(slots=True)
class RuntimeContainer:
    """Aggregates ports/adapters used across application services."""

    config_port: ConfigPort
    ports: Dict[str, Any] = field(default_factory=dict)

    def with_port(self, name: str, port: Any) -> "RuntimeContainer":
        """Return a new container with an additional named port registered."""
        updated = dict(self.ports)
        updated[name] = port
        return RuntimeContainer(config_port=self.config_port, ports=updated)

    def get_port(self, name: str, default: Any = None) -> Any:
        """Retrieve an optional port by name."""
        return self.ports.get(name, default)


def create_runtime_container(
    *,
    config_port: Optional[ConfigPort] = None,
    **ports: Any,
) -> RuntimeContainer:
    """Factory helper to build a runtime container with optional extra ports."""
    cfg_port = config_port or EnvTomlConfig()
    return RuntimeContainer(config_port=cfg_port, ports=dict(ports))


def _get_or_create_container_locked() -> RuntimeContainer:
    global _CONTAINER
    if _CONTAINER is None:
        _CONTAINER = create_runtime_container()
    return _CONTAINER


def get_container() -> RuntimeContainer:
    with _LOCK:
        return _get_or_create_container_locked()


def set_container(container: RuntimeContainer) -> None:
    global _CONTAINER
    with _LOCK:
        _CONTAINER = container


def get_config_port() -> ConfigPort:
    with _LOCK:
        return _get_or_create_container_locked().config_port


def set_config_port(port: ConfigPort) -> None:
    with _LOCK:
        container = _get_or_create_container_locked()
        container.config_port = port


def get_config_snapshot() -> ConfigSnapshot:
    return get_config_port().get()
