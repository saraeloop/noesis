"""Prompt provenance recorder (ADR-005, v0.1 experimental)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Callable, Literal, Mapping, TYPE_CHECKING

from noesis.runtime.serialization import canonical_dumps
from noesis.domain.artifacts.immutability import ArtifactWriteMode
from noesis.runtime.artifacts.immutability import default_artifact_guard

if TYPE_CHECKING:
    from noesis.infrastructure.state_repository import EpisodeContext

PromptProvenanceMode = Literal["full", "hash_only", "redacted"]

__all__ = ["PromptRecorder", "PromptProvenanceMode"]

SCHEMA_NAME = "prompt"
SCHEMA_VERSION = "1.0.0"
PROMPTS_FILE_NAME = "prompts.jsonl"


def _normalize_rendered(rendered: str) -> str:
    """
    Normalize prompt text for deterministic hashing.

    - convert CRLF to LF
    - strip trailing whitespace on each line
    - trim surrounding whitespace
    """
    normalized_lines = [line.rstrip() for line in rendered.replace("\r\n", "\n").splitlines()]
    return "\n".join(normalized_lines).strip()


def _fingerprint(rendered: str) -> tuple[str, str]:
    """Return (fingerprint, normalized_prompt)."""
    normalized = _normalize_rendered(rendered)
    digest = sha256(normalized.encode("utf-8")).hexdigest()
    return f"sha256:{digest}", normalized


def _append_prompt(run_dir: Path, record: Mapping[str, object]) -> None:
    """Append a single prompt record to prompts.jsonl."""
    default_artifact_guard().ensure_write_allowed(
        episode_dir=run_dir,
        artifact=PROMPTS_FILE_NAME,
        mode=ArtifactWriteMode.APPEND,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    payload = canonical_dumps(record)
    with (run_dir / PROMPTS_FILE_NAME).open("a", encoding="utf-8") as handle:
        handle.write(payload + "\n")


@dataclass(slots=True)
class PromptRecord:
    """Structured prompt provenance entry."""

    episode_id: str
    phase: str
    agent_id: str
    fingerprint: str
    timestamp: str
    mode: PromptProvenanceMode
    rendered: str | None
    template: str | None = None
    variables: Mapping[str, object] | None = None
    tags: Mapping[str, str] | None = None
    role: str | None = None
    kind: str | None = None
    model: str | None = None
    template_id: str | None = None
    event_id: str | None = None
    outcome_event_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "$schema_name": SCHEMA_NAME,
            "$schema_version": SCHEMA_VERSION,
            "episode_id": self.episode_id,
            "phase": self.phase,
            "agent_id": self.agent_id,
            "fingerprint": self.fingerprint,
            "timestamp": self.timestamp,
            "mode": self.mode,
        }
        if self.tags:
            payload["tags"] = dict(self.tags)
        if self.template is not None:
            payload["template"] = self.template
        if self.rendered is not None:
            payload["rendered"] = self.rendered
        if self.variables is not None:
            payload["variables"] = dict(self.variables)
        if self.role:
            payload["role"] = self.role
        if self.kind:
            payload["kind"] = self.kind
        if self.model:
            payload["model"] = self.model
        if self.template_id:
            payload["template_id"] = self.template_id
        if self.event_id:
            payload["event_id"] = self.event_id
        if self.outcome_event_id:
            payload["outcome_event_id"] = self.outcome_event_id
        return payload


@dataclass(slots=True)
class PromptRecorder:
    """Append-only prompt recorder used at runtime."""

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

    def record(
        self,
        *,
        phase: str,
        agent_id: str,
        rendered: str,
        role: str | None = None,
        kind: str | None = None,
        model: str | None = None,
        template_id: str | None = None,
        template: str | None = None,
        variables: Mapping[str, object] | None = None,
        tags: Mapping[str, str] | None = None,
        event_id: str | None = None,
        outcome_event_id: str | None = None,
        timestamp: str | None = None,
        now: Callable[[], datetime] | Callable[[], str] | None = None,
    ) -> None:
        """
        Persist a prompt provenance entry.

        `rendered` is normalized before hashing. When the recorder is disabled
        the method returns immediately without touching the filesystem.
        """
        if not self.enabled:
            return

        observed_at = timestamp
        if observed_at is None:
            if now is not None:
                current = now()
                observed_at = current if isinstance(current, str) else current.isoformat()
            else:
                observed_at = datetime.now(timezone.utc).isoformat()

        fingerprint, normalized = _fingerprint(rendered)

        def _redacted(value: str | None) -> str | None:
            if value is None:
                return None
            return "__redacted__"

        stored_rendered: str | None = normalized
        stored_template = template
        stored_variables = variables

        if self.mode == "hash_only":
            stored_rendered = None
            stored_template = None
            stored_variables = None
        elif self.mode == "redacted":
            stored_rendered = _redacted(normalized)
            stored_template = _redacted(template)
            stored_variables = None

        record = PromptRecord(
            episode_id=self.episode_id,
            phase=phase,
            agent_id=agent_id,
            rendered=stored_rendered,
            template=stored_template,
            variables=stored_variables,
            tags=tags,
            fingerprint=fingerprint,
            timestamp=observed_at,
            mode=self.mode,
            role=role,
            kind=kind,
            model=model,
            template_id=template_id,
            event_id=event_id,
            outcome_event_id=outcome_event_id,
        )
        _append_prompt(self.run_dir, record.to_dict())
