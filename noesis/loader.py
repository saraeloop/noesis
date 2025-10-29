"""
Noēsis dynamic flow/graph loader.

Resolves an execution target from:
  • Simple names (e.g., "react") → tries `flows.react` then `noesis_user.react`
  • Dotted factories ("pkg.mod:make" or "pkg.mod:create") → imports & calls zero-arg factory
  • Local paths (file or package dir) → imports module and calls a zero-arg factory
  • Callables → calls and returns the instance
  • Concrete objects → returned as-is

Design goals:
  • Zero coupling to core I/O (avoid circular imports)
  • Convention over configuration (common factory names: make/build/create/…)
  • Helpful errors when resolution fails
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Union
import importlib.util

GraphSource = Union[str, Callable[[], Any], Any]


def load_graph(source: GraphSource) -> Any:
    """Resolve and instantiate a user flow/graph from a name, dotted factory,
    filesystem path, callable, or concrete object."""
    if callable(source):
        return source()

    if isinstance(source, str):
        # Dotted factory: "pkg.mod:factory"
        if ":" in source:
            mod_path, factory_name = source.split(":", 1)
            mod = __import__(mod_path, fromlist=[factory_name])
            factory = getattr(mod, factory_name)
            return factory()

        p = Path(source)
        if p.exists():
            return _load_from_path(p)

        # Name-only: try `flows.<name>` then `noesis_user.<name>`
        for pkg in ("flows", "noesis_user"):
            try:
                mod = __import__(f"{pkg}.{source}", fromlist=["*"])
                # try common factory names
                for fname in ("make", "build", "create", "factory", "make_graph", "build_graph"):
                    if hasattr(mod, fname):
                        return getattr(mod, fname)()
                # fallback to module-level object
                for objname in ("graph", "flow", "app"):
                    if hasattr(mod, objname):
                        return getattr(mod, objname)
            except Exception:
                continue
        raise ValueError(f"could not resolve '{source}' as dotted path, file, or known name")

    # already a concrete object
    return source


def _load_from_path(path: Path) -> Any:
    """Import a module from a file or package directory and return a graph via
    a zero-arg factory (make/build/create/…) or a module-level object (graph/flow/app)."""
    if path.is_dir():
        path = path / "__init__.py"
    spec = importlib.util.spec_from_file_location("noesis_user_graph", str(path))
    if not spec or not spec.loader:
        raise ImportError(f"cannot import module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # factories
    for fname in ("make", "build", "create", "factory", "make_graph", "build_graph"):
        if hasattr(mod, fname):
            return getattr(mod, fname)()
    # module-level object
    for objname in ("graph", "flow", "app"):
        if hasattr(mod, objname):
            return getattr(mod, objname)
    raise ValueError(f"no suitable factory or object found in {path}")