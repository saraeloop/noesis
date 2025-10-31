"""
Compatibility shim for the legacy ``noesis.config`` module.

Importing this module directly is deprecated; use ``noesis.set(...)`` and
related public APIs instead. Internal modules should import
``noesis._config``.
"""

from __future__ import annotations

import sys
import warnings

from ._config import (  # noqa: F401
    get,
    set,
    reset,
    reload_from_disk_and_env,
)

_parent = sys.modules.get("noesis", sys.modules[__name__])
if not getattr(_parent, "_config_shim_warned", False):
    warnings.warn(
        "noesis.config is legacy and will be removed in v0.6. "
        "Use noesis.set(...) / noesis.summary(...) etc. instead.",
        FutureWarning,
        stacklevel=2,
    )
    _parent._config_shim_warned = True

__all__ = ["get", "set", "reset", "reload_from_disk_and_env"]
