"""Deterministic fingerprint helpers for protocol-first tool artifacts."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .enums import ToolProtocol
from .models import ToolIdentity


def canonical_json(value: Any) -> str:
    """Serialize a value into a deterministic JSON representation."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def fingerprint_payload(payload: Mapping[str, Any]) -> str:
    """Fingerprint a normalized payload deterministically."""

    return _sha256(canonical_json(payload))


def fingerprint_prepared_invocation(
    *,
    protocol: ToolProtocol | str,
    tool: ToolIdentity,
    normalized_payload: Mapping[str, Any],
) -> str:
    """Fingerprint the contract-relevant parts of a prepared invocation."""

    canonical = {
        "protocol": str(getattr(protocol, "value", protocol)),
        "tool": {
            "namespace": tool.namespace,
            "name": tool.name,
            "version": tool.version,
        },
        "payload": normalized_payload,
    }
    return _sha256(canonical_json(canonical))


def _sha256(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


__all__ = [
    "canonical_json",
    "fingerprint_payload",
    "fingerprint_prepared_invocation",
]
