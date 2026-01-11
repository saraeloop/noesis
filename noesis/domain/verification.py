"""
Domain models for verification metadata.

These entities represent audit metadata rather than evidence artifacts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class SnapshotCaptureTimes:
    """Capture timestamps for snapshot phases."""

    pre: str | None = None
    post: str | None = None

    def with_pre(self, timestamp: str) -> "SnapshotCaptureTimes":
        return SnapshotCaptureTimes(pre=timestamp, post=self.post)

    def with_post(self, timestamp: str) -> "SnapshotCaptureTimes":
        return SnapshotCaptureTimes(pre=self.pre, post=timestamp)

    def to_dict(self) -> dict[str, str | None]:
        return {"pre": self.pre, "post": self.post}

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "SnapshotCaptureTimes":
        pre = data.get("pre")
        post = data.get("post")
        if pre is not None and not isinstance(pre, str):
            raise ValueError("SnapshotCaptureTimes.pre must be a string or null.")
        if post is not None and not isinstance(post, str):
            raise ValueError("SnapshotCaptureTimes.post must be a string or null.")
        return cls(pre=pre, post=post)


__all__ = ["SnapshotCaptureTimes"]
