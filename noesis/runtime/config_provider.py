"""Shared runtime context that wires versioned ports."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Dict, Optional

from noesis.interfaces.config import ConfigPort, ConfigSnapshot
from noesis.infrastructure.config import EnvTomlConfig

__all__ = [
    "RuntimeContext",
    "create_runtime_context",
    "get_context",
    "set_context",
    "get_config_port",
    "set_config_port",
    "get_config_snapshot",
]

_LOCK = RLock()
_CONTEXT: Optional["RuntimeContext"] = None


@dataclass(frozen=True, slots=True)
class _PortBinding:
    name: str
    api: str
    provider: Any


@dataclass(slots=True)
class RuntimeContext:
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


def create_runtime_context(
    *,
    config_port: Optional[ConfigPort] = None,
    ports: Optional[Dict[str, tuple[Any, str]]] = None,
) -> RuntimeContext:
    cfg_port = config_port or EnvTomlConfig()
    context = RuntimeContext(config_port=cfg_port)
    for name, (provider, api) in (ports or {}).items():
        context.register(name, provider, api=api)
    return context


def _get_or_create_context_locked() -> RuntimeContext:
    global _CONTEXT
    if _CONTEXT is None:
        _CONTEXT = create_runtime_context()
    return _CONTEXT


def get_context() -> RuntimeContext:
    with _LOCK:
        return _get_or_create_context_locked()


def set_context(context: RuntimeContext) -> None:
    global _CONTEXT
    with _LOCK:
        _CONTEXT = context


def get_config_port() -> ConfigPort:
    with _LOCK:
        context = _get_or_create_context_locked()
        required_api = getattr(context.config_port, "__api_version__", "config/unknown")
        return context.require("config", required_api)


def set_config_port(port: ConfigPort) -> None:
    with _LOCK:
        context = _get_or_create_context_locked()
        context.config_port = port
        context.register("config", port, api=getattr(port, "__api_version__", "config/unknown"))


def get_config_snapshot() -> ConfigSnapshot:
    return get_config_port().get()
