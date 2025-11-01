"""
Public configuration facade for Noēsis.

This module exposes the typed runtime configuration model and the default
environment/TOML loader without leaking the internal infrastructure package
structure. Applications should import from here instead of
`noesis.infrastructure.config`.
"""

from __future__ import annotations

from .domain.config import (
    CONFIG_FILE_CANDIDATES,
    RuntimeConfig,
    apply_runtime_overrides,
    default_runtime_config,
)
from .infrastructure.config import EnvTomlConfig

__all__ = [
    "EnvTomlConfig",
    "RuntimeConfig",
    "default_runtime_config",
    "apply_runtime_overrides",
    "CONFIG_FILE_CANDIDATES",
]
