"""
Noēsis dynamic flow/graph loader.

Resolves an execution target from:
  • Simple names (e.g., "react") → tries `flows.react` then `noesis_user.react`
  • Dotted factories ("pkg.mod:make") → imports & calls zero-arg factory (or returns executor/object)
  • Local paths (file or package dir) → imports module and calls a zero-arg factory
  • Callables → calls ONLY if it is a zero-arg factory; otherwise treated as an executor
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
import inspect

GraphSource = Union[str, Callable[..., Any], Any]

_FACTORY_NAMES = ("make", "build", "create", "factory", "make_graph", "build_graph")
_OBJECT_NAMES = ("graph", "flow", "app")


def _is_executor_like(obj: Any) -> bool:
    """
    Heuristic: treat as an executor if it:
      - is an instance (not a class) that exposes execute()/invoke(), OR
      - is callable but requires at least one argument (e.g., __call__(task))
    This prevents calling adapter instances as zero-arg factories.
    
    Note: Classes are NOT treated as executor-like, even if they have invoke/execute
    methods, because calling invoke() on a class would fail (self not bound).
    """
    # Do not treat classes as executor-like instances
    if inspect.isclass(obj):
        return False
    
    if hasattr(obj, "execute") or hasattr(obj, "invoke"):
        return True

    if callable(obj):
        # If it is callable and requires args, it is likely an executor interface.
        if not _is_zero_arg_callable(obj):
            return True

    return False


def _is_zero_arg_callable(fn: Any) -> bool:
    """
    Returns True if `fn()` can be called with zero arguments (by signature),
    i.e., no required positional-or-keyword params.

    Notes:
      - Works for functions, bound methods, and callable instances.
      - For callable instances, inspects __call__().
    """
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        # If we cannot introspect, be conservative: do NOT treat as zero-arg factory.
        return False

    for p in sig.parameters.values():
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            # *args/**kwargs means it *can* accept zero args.
            continue
        if p.default is inspect._empty:
            # required param => not zero-arg callable
            return False
    return True


def load_graph(source: GraphSource) -> Any:
    """Resolve and instantiate a user flow/graph from a name, dotted factory,
    filesystem path, callable, or concrete object."""
    # 1) If it's already an executor-like instance, return as-is.
    if _is_executor_like(source):
        return source

    # 2) If it's a callable, only call it if it is a zero-arg factory.
    if callable(source):
        if _is_zero_arg_callable(source):
            return source()
        # Callable but not zero-arg: treat as an executor object.
        return source

    # 3) String resolution
    if isinstance(source, str):
        # Dotted factory: "pkg.mod:factory"
        if ":" in source:
            mod_path, factory_name = source.split(":", 1)
            mod = __import__(mod_path, fromlist=[factory_name])
            attr = getattr(mod, factory_name)

            if _is_executor_like(attr):
                return attr
            if callable(attr) and _is_zero_arg_callable(attr):
                return attr()
            return attr  # concrete object

        p = Path(source)
        if p.exists():
            return _load_from_path(p)

        # Name-only: try `flows.<name>` then `noesis_user.<name>`
        for pkg in ("flows", "noesis_user"):
            try:
                mod = __import__(f"{pkg}.{source}", fromlist=["*"])
                # try common factory names
                for fname in _FACTORY_NAMES:
                    if hasattr(mod, fname):
                        factory = getattr(mod, fname)
                        if callable(factory) and _is_zero_arg_callable(factory):
                            return factory()
                        return factory
                # fallback to module-level object
                for objname in _OBJECT_NAMES:
                    if hasattr(mod, objname):
                        return getattr(mod, objname)
            except Exception:
                continue

        raise ValueError(
            f"could not resolve '{source}' as dotted factory, filesystem path, or known name "
            f"(tried flows.<name> and noesis_user.<name>)"
        )

    # 4) Concrete object
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
    for fname in _FACTORY_NAMES:
        if hasattr(mod, fname):
            factory = getattr(mod, fname)
            if callable(factory) and _is_zero_arg_callable(factory):
                return factory()
            return factory

    # module-level object
    for objname in _OBJECT_NAMES:
        if hasattr(mod, objname):
            return getattr(mod, objname)

    raise ValueError(f"no suitable factory or object found in {path}")