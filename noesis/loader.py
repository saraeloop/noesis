"""
Dynamic graph loader. No dependencies on core/io to avoid circular imports.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Union
import importlib.util

GraphSource = Union[str, Callable[[], Any], Any]


def load_graph(source: GraphSource) -> Any:
    """
    Accepts:
      • Registered/simple name (e.g., "react") → try `flows.react` then `noesis_user.react`
      • Dotted factory "pkg.mod:make" → import and call zero-arg factory
      • Local path to file/dir → import module and call a zero-arg factory if present
      • Callable → call to get instance
      • Object → return as-is
    """
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