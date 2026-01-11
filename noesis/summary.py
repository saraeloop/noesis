"""
Public summary helpers.

Exposes convenience functions for loading and finalising summaries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .deprecated import emit_legacy_warning, legacy_shims_enabled
from .io import summary as _summary_fn
from .runtime.summary import finalize_summary as _finalize_summary

__all__ = ["read", "finalize"]


def read(episode_id: str, *, context: Any | None = None) -> Dict[str, Any]:
    """Return the parsed summary JSON for an episode."""
    return _summary_fn(episode_id, context=context)


def finalize(
    *,
    run_dir: Path,
    episode_id: str,
    task: str,
    seed: int,
    started_at: str,
    intuition_enabled: bool,
    intuition_mode: Any,
    using_label: Optional[str],
    tags: Optional[Dict[str, Any]],
    intuition: Any,
    schema_version: str,
    config: Any,
    ports: Dict[str, str],
    adapter_result: str,
    outcome: str,
    verification: Dict[str, object | None],
) -> None:
    """Public alias for `finalize_summary`."""
    _finalize_summary(
        run_dir=run_dir,
        episode_id=episode_id,
        task=task,
        seed=seed,
        started_at=started_at,
        intuition_enabled=intuition_enabled,
        intuition_mode=intuition_mode,
        using_label=using_label,
        tags=tags,
        intuition=intuition,
        schema_version=schema_version,
        config=config,
        ports=ports,
        adapter_result=adapter_result,
        outcome=outcome,
        verification=verification,
    )


if legacy_shims_enabled():
    def load(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        emit_legacy_warning("noesis.summary.load")
        return read(*args, **kwargs)

    def finalize_summary(*args: Any, **kwargs: Any) -> None:
        emit_legacy_warning("noesis.summary.finalize_summary")
        finalize(*args, **kwargs)

    __all__ += ["load", "finalize_summary"]
