from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import UUID, uuid5
import hashlib
import os
import threading
import time

ULID_ALPHABET: Final[str] = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_TIMESTAMP_MASK: Final[int] = (1 << 48) - 1
_RANDOM_MASK: Final[int] = (1 << 80) - 1

_DIRECTIVE_ROOT_NAMESPACE = UUID("5c41078f-64dc-42c1-a9b2-e3ea2df5f6d5")
_GOVERNANCE_ROOT_NAMESPACE = UUID("3a326538-7b7b-4d4f-8dbd-818842d4a1d0")

_ulid_lock = threading.Lock()
_last_timestamp_ms = -1
_last_entropy = 0


def _encode_base32(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(ULID_ALPHABET[value & 0x1F])
        value >>= 5
    chars.reverse()
    return "".join(chars)


def new_episode_ulid(seed: int = 0, *, timestamp_ms: int | None = None) -> str:
    """
    Return a monotonic-friendly ULID string (26 Crockford base32 chars).

    The optional `seed` perturbs the entropy component to reduce collisions when
    multiple runs share the same millisecond timestamp.
    """
    global _last_timestamp_ms, _last_entropy
    with _ulid_lock:
        ts_ms = _current_ms() if timestamp_ms is None else timestamp_ms & _TIMESTAMP_MASK
        entropy = _random_entropy(seed)
        if ts_ms < _last_timestamp_ms:
            ts_ms = _last_timestamp_ms
        if ts_ms == _last_timestamp_ms:
            if _last_entropy == _RANDOM_MASK:
                ts_ms = _wait_next_ms(ts_ms)
                entropy = _random_entropy(seed)
                _assign_state(ts_ms, entropy)
            else:
                entropy = (_last_entropy + 1) & _RANDOM_MASK
                _assign_state(ts_ms, entropy)
        else:
            _assign_state(ts_ms, entropy)
        return _encode_base32(ts_ms, 10) + _encode_base32(entropy, 16)


def _current_ms() -> int:
    return int(time.time_ns() // 1_000_000) & _TIMESTAMP_MASK


def _wait_next_ms(current: int) -> int:
    global _last_timestamp_ms
    while True:
        candidate = _current_ms()
        if candidate > current:
            _last_timestamp_ms = candidate
            return candidate
        time.sleep(0.0001)


def _random_entropy(seed: int) -> int:
    entropy = int.from_bytes(os.urandom(10), "big") & _RANDOM_MASK
    if seed:
        seed_bytes = hashlib.blake2b(str(seed).encode("utf-8"), digest_size=10).digest()
        entropy ^= int.from_bytes(seed_bytes, "big")
        entropy &= _RANDOM_MASK
    return entropy


def _assign_state(timestamp_ms: int, entropy: int) -> None:
    global _last_timestamp_ms, _last_entropy
    _last_timestamp_ms = timestamp_ms
    _last_entropy = entropy & _RANDOM_MASK


def _extract_ulid(episode_id: str) -> str:
    """Best-effort extraction of the ULID component from an episode ID."""
    if episode_id.startswith("ep_"):
        candidate = episode_id[3:]
        if "_s" in candidate:
            candidate = candidate.split("_s", 1)[0]
        if len(candidate) >= 26:
            return candidate[:26]
        return candidate
    return episode_id


@dataclass(frozen=True, slots=True)
class EpisodeIds:
    """Aggregated identifiers derived from a ULID episode root."""

    ulid: str
    episode_id: str
    directive_namespace: UUID
    governance_namespace: UUID

    @classmethod
    def mint(cls, *, seed: int = 0, timestamp_ms: int | None = None) -> "EpisodeIds":
        ulid = new_episode_ulid(seed, timestamp_ms=timestamp_ms)
        episode_id = f"ep_{ulid}"
        directive_ns = uuid5(_DIRECTIVE_ROOT_NAMESPACE, ulid)
        governance_ns = uuid5(_GOVERNANCE_ROOT_NAMESPACE, ulid)
        return cls(
            ulid=ulid,
            episode_id=episode_id,
            directive_namespace=directive_ns,
            governance_namespace=governance_ns,
        )

    @classmethod
    def from_episode(cls, episode_id: str) -> "EpisodeIds":
        ulid = _extract_ulid(episode_id)
        directive_ns = uuid5(_DIRECTIVE_ROOT_NAMESPACE, ulid)
        governance_ns = uuid5(_GOVERNANCE_ROOT_NAMESPACE, ulid)
        return cls(
            ulid=ulid,
            episode_id=episode_id,
            directive_namespace=directive_ns,
            governance_namespace=governance_ns,
        )

    def directive(self, *, step_index: int, rule: str) -> UUID:
        token = f"{step_index}:{rule}"
        return uuid5(self.directive_namespace, token)

    def governance(self, *, rule_id: str) -> UUID:
        return uuid5(self.governance_namespace, rule_id)


def directive_uuid(episode_id: str, step_index: int, rule: str) -> UUID:
    """Derive a deterministic UUID for a directive emitted during an episode."""
    ids = EpisodeIds.from_episode(episode_id)
    return ids.directive(step_index=step_index, rule=rule)


def governance_uuid(episode_id: str, rule_id: str) -> UUID:
    """Derive a deterministic UUID for a governance decision."""
    ids = EpisodeIds.from_episode(episode_id)
    return ids.governance(rule_id=rule_id)


__all__ = [
    "EpisodeIds",
    "directive_uuid",
    "governance_uuid",
    "new_episode_ulid",
]
