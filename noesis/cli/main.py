from __future__ import annotations

from typing import Optional, Sequence

from .__main__ import _fetch_recent_episodes, _render_home, _select_renderer as _select_renderer_impl, main, _HAS_RICH
from .context import GlobalOptions

__all__ = ["main", "_fetch_recent_episodes", "_render_home", "_select_renderer", "_HAS_RICH"]


def _select_renderer(ctx, options: GlobalOptions):
    return _select_renderer_impl(
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
