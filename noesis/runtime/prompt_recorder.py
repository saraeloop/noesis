"""
Prompt provenance recorder skeleton (ADR-005).

This utility will eventually stream prompt metadata into `prompts.jsonl`.
For v0.1 it only reflects configuration so call sites can branch on
`enabled` and `mode` without touching file I/O yet.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from noesis.infrastructure.state_repository import EpisodeContext

PromptProvenanceMode = Literal["full", "hash_only"]

__all__ = ["PromptRecorder", "PromptProvenanceMode"]


@dataclass(slots=True)
class PromptRecorder:
    """Minimal prompt recorder facade used by the runtime."""

    run_dir: Path
    episode_id: str
    enabled: bool
    mode: PromptProvenanceMode

    @classmethod
    def from_context(cls, context: "EpisodeContext") -> "PromptRecorder":
        """
        Build a recorder by inspecting episode-level provenance settings.

        The recorder keeps a reference to the run directory and episode ID so
        future iterations can emit `prompts.jsonl` without additional wiring.
        """
        return cls(
            run_dir=context.run_dir,
            episode_id=context.episode_id,
            enabled=context.prompt_provenance_enabled,
            mode=context.prompt_provenance_mode,
        )

    def is_enabled(self) -> bool:
        """Return True when prompt provenance capture should run."""
        return self.enabled

    def record(self, **_: object) -> None:
        """
        Placeholder recording hook.

        Future versions will hash and persist prompt bodies. For now we no-op,
        which keeps deterministic behavior unchanged while the feature flag is off.
        """
        return None

