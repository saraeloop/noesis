from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
    from .context import GlobalOptions

__all__ = ["main", "_fetch_recent_episodes", "_render_home", "_select_renderer", "_HAS_RICH"]


def _check_has_rich() -> bool:
    """Check if Rich is available."""
    try:
        import rich  # noqa: F401
        return True
    except ImportError:
        return False


# Lazy evaluation - only check once when accessed
_HAS_RICH: bool = _check_has_rich()


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Main CLI entrypoint. Lazily imports __main__ to avoid import-time side effects."""
    from .__main__ import main as _main_impl
    return _main_impl(list(argv) if argv is not None else None)


def _fetch_recent_episodes(*args, **kwargs):
    """Lazy wrapper for _fetch_recent_episodes."""
    from .__main__ import _fetch_recent_episodes as _impl
    return _impl(*args, **kwargs)


def _render_home(*args, **kwargs):
    """Lazy wrapper for _render_home."""
    from .__main__ import _render_home as _impl
    return _impl(*args, **kwargs)


def _select_renderer(ctx, options: "GlobalOptions"):
    """Lazy wrapper for _select_renderer."""
    from .__main__ import _select_renderer as _impl
    return _impl(
        ctx,
        json_output=options.json,
        quiet=options.quiet,
        force_rich=options.force_rich,
    )


def cli(argv: Optional[Sequence[str]] = None) -> int:
    """Backward-compatible CLI entrypoint."""
    return main(list(argv) if argv is not None else None)


def _as_callable_module() -> None:
    """Allow this module to be called like a function in tests."""
    import sys
    import types

    class _CallableModule(types.ModuleType):
        def __call__(self, argv: Optional[Sequence[str]] = None) -> int:  # type: ignore[override]
            return main(list(argv) if argv is not None else None)

    module = sys.modules.get(__name__)
    if module is not None and not isinstance(module, _CallableModule):
        module.__class__ = _CallableModule


_as_callable_module()
