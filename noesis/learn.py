"""Learning utilities wrapping domain models with persistence helpers."""

from __future__ import annotations

__all__ = [
    "LearnMode",
    "LearnStatus",
    "LearnProposal",
    "LearnCausalityError",
    "MissingCausalLinkError",
    "build_learn_payload",
    "persist_episode_learning",
    "load_policy_snapshot",
    "update_policy_snapshot",
    "derive_target_key",
    "summarise_learn_kinds",
    "emit",
    "maybe_emit_learn_event",
]


from noesis.domain.learning.errors import LearnCausalityError, MissingCausalLinkError
from noesis.runtime.learning import (
    LearnMode,
    LearnProposal,
    LearnStatus,
    build_learn_payload,
    derive_target_key,
    load_policy_snapshot,
    maybe_emit_learn_event,
    persist_episode_learning,
    summarise_learn_kinds,
    update_policy_snapshot,
)

emit = maybe_emit_learn_event
