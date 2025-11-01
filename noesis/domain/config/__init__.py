"""
Domain-level configuration primitives for Noēsis.

This package defines pure data structures and validation helpers that model
runtime configuration without introducing infrastructure concerns.
"""

from .settings import (
    ALLOWED_CONFIG_KEYS,
    CONFIG_FILE_CANDIDATES,
    RuntimeConfig,
    apply_runtime_overrides,
    default_runtime_config,
)

__all__ = [
    "ALLOWED_CONFIG_KEYS",
    "CONFIG_FILE_CANDIDATES",
    "RuntimeConfig",
    "apply_runtime_overrides",
    "default_runtime_config",
]
