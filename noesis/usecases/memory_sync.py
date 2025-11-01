"""Application service for persisting episode summaries into long-term memory."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from ..domain.memory import build_episode_fact
from ..interfaces.memory import Fact
from ..runtime.config_provider import RuntimeContext
from ..trace.events import write_event
from ..trace.summary import read_summary

LONG_TERM_CAPABILITY = "long_term_memory"

__all__ = ["persist_episode_memory", "LONG_TERM_CAPABILITY"]


def _write_memory_event(run_dir: Path, episode_id: str, payload: Dict[str, Any]) -> None:
    write_event(
        run_dir,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "episode_id": episode_id,
            "agent_id": "memory",
            "phase": "memory",
            "payload": payload,
            "evidence_ids": [],
        },
    )


def persist_episode_memory(
    *,
    run_dir: Path,
    context: RuntimeContext,
    capability: str = LONG_TERM_CAPABILITY,
) -> None:
    """Persist the episode summary into the configured long-term memory."""
    try:
        summary = read_summary(run_dir)
    except Exception as exc:  # noqa: BLE001
        _write_memory_event(
            run_dir,
            episode_id="unknown",
            payload={
                "status": "error",
                "capability": capability,
                "error": f"read_summary_failed: {exc}",
            },
        )
        return

    episode_id = str(summary.get("episode_id") or "unknown")

    try:
        memory_port = context.resolve("memory")
    except KeyError:
        _write_memory_event(
            run_dir,
            episode_id=episode_id,
            payload={
                "status": "skipped",
                "reason": "port_missing",
                "capability": capability,
            },
        )
        return

    if not memory_port.supports(capability):
        _write_memory_event(
            run_dir,
            episode_id=episode_id,
            payload={"status": "skipped", "reason": "capability_missing", "capability": capability},
        )
        return

    try:
        fact: Fact = build_episode_fact(summary, run_dir=run_dir)
        memory_port.write_fact(fact)
        memory_port.link_episode(episode_id, [fact.id])
        _write_memory_event(
            run_dir,
            episode_id=episode_id,
            payload={
                "status": "persisted",
                "fact_id": fact.id,
                "capability": capability,
                "artifacts": fact.metadata.get("artifacts", {}),
            },
        )
    except Exception as exc:  # noqa: BLE001
        _write_memory_event(
            run_dir,
            episode_id=episode_id,
            payload={
                "status": "error",
                "capability": capability,
                "error": str(exc),
            },
        )
