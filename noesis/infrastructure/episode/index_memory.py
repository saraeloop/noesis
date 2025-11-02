"""
In-memory (filesystem) episode index implementation.

Persists a JSONL manifest of episodes and optionally maintains a FAISS-backed
similarity index when embeddings are provided.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple
import json
import threading

from noesis.interfaces.episode import EpisodeIndexPort, EpisodeRecord

try:  # pragma: no cover - optional dependency
    import faiss  # type: ignore
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    faiss = None  # type: ignore[assignment]
    _np = None  # type: ignore[assignment]

__all__ = ["EpisodeIndex"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _parse_iso(ts: str) -> datetime:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError as err:  # pragma: no cover - defensive
        raise ValueError(f"invalid ISO timestamp: {ts}") from err


class _FaissHelper:
    """Minimal FAISS wrapper that persists vectors alongside the JSONL log."""

    def __init__(self, base_path: Path) -> None:
        self.enabled = faiss is not None and _np is not None
        self.base_path = base_path
        self.index_path = base_path.with_suffix(".faiss")
        self.meta_path = base_path.with_suffix(".meta.json")
        self._lock = threading.Lock()
        self._index = None
        self._ids: List[str] = []
        if self.enabled:
            self._load()

    def _load(self) -> None:
        if not self.enabled:
            return
        if self.index_path.exists():
            self._index = faiss.read_index(str(self.index_path))
        if self.meta_path.exists():
            with self.meta_path.open("r", encoding="utf-8") as handle:
                self._ids = json.load(handle)

    def _persist(self) -> None:
        if not self.enabled or self._index is None:
            return
        faiss.write_index(self._index, str(self.index_path))
        with self.meta_path.open("w", encoding="utf-8") as handle:
            json.dump(self._ids, handle, ensure_ascii=False)

    def add(self, episode_id: str, embedding: Iterable[float]) -> None:
        if not self.enabled:
            return
        vector = _np.asarray(list(embedding), dtype="float32")
        if vector.ndim != 1:
            raise ValueError("embedding must be a 1-D iterable")
        with self._lock:
            if self._index is None:
                dim = vector.shape[0]
                self._index = faiss.IndexFlatL2(dim)
            elif vector.shape[0] != self._index.d:
                raise ValueError(f"embedding dim {vector.shape[0]} != index dim {self._index.d}")
            self._index.add(vector.reshape(1, -1))
            self._ids.append(episode_id)
            self._persist()

    def search(self, embedding: Iterable[float], k: int = 5) -> List[Tuple[str, float]]:
        if not self.enabled or self._index is None:
            return []
        vector = _np.asarray(list(embedding), dtype="float32")
        if vector.shape[0] != self._index.d:
            raise ValueError(f"embedding dim {vector.shape[0]} != index dim {self._index.d}")
        distances, indices = self._index.search(vector.reshape(1, -1), min(k, self._index.ntotal))
        results: List[Tuple[str, float]] = []
        for idx, score in zip(indices[0], distances[0]):
            if idx < 0 or idx >= len(self._ids):
                continue
            results.append((self._ids[idx], float(score)))
        return results


class EpisodeIndex(EpisodeIndexPort):
    """
    Append-only episode manifest with optional FAISS-backed similarity index.

    Parameters
    ----------
    root : Path-like
        Directory where the JSONL log and optional FAISS files live.
    ttl_days : int | None
        If provided, records older than the TTL are marked with an expires_at.
    enable_faiss : bool
        When True and FAISS + NumPy are available, embeddings passed to
        `append()` are stored in a vector index for similarity queries.
    """

    def __init__(
        self,
        root: Path | str,
        *,
        ttl_days: Optional[int] = None,
        enable_faiss: bool = False,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "episodes.jsonl"
        self.ttl_days = ttl_days if ttl_days is None else float(ttl_days)
        self._faiss = _FaissHelper(self.root / "episodes.index") if enable_faiss else None
        self._lock = threading.Lock()

    def append(
        self,
        *,
        episode_id: str,
        summary_path: Path | str,
        state_path: Path | str,
        status: str,
        task: str,
        using: Optional[str],
        provenance: Optional[Dict[str, str]] = None,
        embedding: Optional[Iterable[float]] = None,
    ) -> EpisodeRecord:
        created = _now()
        expires_at = None
        if self.ttl_days is not None:
            expires_at = created + timedelta(days=self.ttl_days)
        record = EpisodeRecord(
            episode_id=episode_id,
            created_at=_iso(created),
            summary_path=str(summary_path),
            state_path=str(state_path),
            status=status,
            task=task,
            using=using,
            expires_at=_iso(expires_at) if expires_at else None,
            provenance=dict(provenance or {}),
        )
        record.provenance.setdefault("schema", "state/1.0")
        record.provenance.setdefault("recorded_by", "core")
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        if self._faiss and embedding is not None:
            self._faiss.add(episode_id, embedding)
        return record

    def iter(self, *, include_expired: bool = False) -> Iterator[EpisodeRecord]:
        if not self.path.exists():
            return
        now = _now()
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                expires_at = payload.get("expires_at")
                if expires_at and not include_expired and _parse_iso(expires_at) <= now:
                    continue
                yield EpisodeRecord(
                    episode_id=payload["episode_id"],
                    created_at=payload["created_at"],
                    summary_path=payload["summary_path"],
                    state_path=payload["state_path"],
                    status=payload["status"],
                    task=payload["task"],
                    using=payload.get("using"),
                    expires_at=expires_at,
                    provenance=payload.get("provenance", {}),
                )

    def vacuum(self) -> int:
        """Rewrite the log excluding expired records. Returns the count removed."""
        if not self.path.exists():
            return 0
        kept: List[str] = []
        removed = 0
        now = _now()
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                expires_at = payload.get("expires_at")
                if expires_at and _parse_iso(expires_at) <= now:
                    removed += 1
                    continue
                kept.append(json.dumps(payload, ensure_ascii=False))
        if removed:
            tmp = self.path.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8") as handle:
                for row in kept:
                    handle.write(row + "\n")
            tmp.replace(self.path)
        return removed

    def search(self, embedding: Iterable[float], k: int = 5) -> Sequence[Tuple[str, float]]:
        """Similarity search over stored embeddings. Empty list if disabled."""
        if not self._faiss:
            return []
        return self._faiss.search(embedding, k=k)
