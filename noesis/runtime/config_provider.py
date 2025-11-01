"""Shared runtime container that wires versioned ports."""

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


@dataclass(frozen=True, slots=True)
class _PortBinding:
    name: str
    api: str
    provider: Any


@dataclass(slots=True)
class RuntimeContainer:
    """Aggregates and validates runtime ports."""

    config_port: ConfigPort
    _registry: Dict[str, _PortBinding] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.register("config", self.config_port, api=getattr(self.config_port, "__api_version__", "config/unknown"))

    def register(self, name: str, provider: Any, *, api: str) -> None:
        if not name:
            raise ValueError("Port name must be provided.")
        if "/" not in api:
            raise ValueError(f"Port API string must follow '<domain>/<version>' pattern, got {api!r}")
        declared = getattr(provider, "__api_version__", api)
        if declared != api:
            raise ValueError(f"Port {name!r} declares API {declared!r}, expected {api!r}")
        self._registry[name] = _PortBinding(name=name, api=api, provider=provider)

    def resolve(self, name: str) -> Any:
        binding = self._registry.get(name)
        if not binding:
            raise KeyError(f"Port '{name}' is not registered.")
        return binding.provider

    def require(self, name: str, api: str) -> Any:
        binding = self._registry.get(name)
        if not binding:
            raise LookupError(f"Port '{name}' is required but not registered.")
        if binding.api != api:
            raise RuntimeError(f"Port '{name}' provides {binding.api}, required {api}.")
        return binding.provider

    def list_ports(self) -> Dict[str, str]:
        return {name: binding.api for name, binding in self._registry.items()}


def create_runtime_container(
    *,
    config_port: Optional[ConfigPort] = None,
    ports: Optional[Dict[str, tuple[Any, str]]] = None,
) -> RuntimeContainer:
    cfg_port = config_port or EnvTomlConfig()
    container = RuntimeContainer(config_port=cfg_port)
    for name, (provider, api) in (ports or {}).items():
        container.register(name, provider, api=api)
    return container


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
        container = _get_or_create_container_locked()
        required_api = getattr(container.config_port, "__api_version__", "config/unknown")
        return container.require("config", required_api)


def set_config_port(port: ConfigPort) -> None:
    with _LOCK:
        container = _get_or_create_container_locked()
        container.config_port = port
        container.register("config", port, api=getattr(port, "__api_version__", "config/unknown"))


def get_config_snapshot() -> ConfigSnapshot:
    return get_config_port().get()
