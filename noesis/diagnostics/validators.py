from __future__ import annotations

import re

_STATE_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def is_valid_sha256_state_hash(value: str) -> bool:
    return bool(value) and bool(_STATE_HASH_RE.match(value))
