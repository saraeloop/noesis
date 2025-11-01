"""SQLite-backed implementation of the MemoryPort contract."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from ...interfaces.memory import Fact, MemoryPort, MemoryQuery

__all__ = ["SQLiteMemory"]

_CREATE_FACTS_TABLE = """
CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

_CREATE_EPISODE_FACTS_TABLE = """
CREATE TABLE IF NOT EXISTS episode_facts (
    episode_id TEXT NOT NULL,
    fact_id TEXT NOT NULL,
    PRIMARY KEY (episode_id, fact_id),
    FOREIGN KEY (fact_id) REFERENCES facts(id) ON DELETE CASCADE
);
"""


@dataclass(slots=True)
class SQLiteMemory(MemoryPort):
    """Simple long-term memory adapter backed by SQLite."""

    db_path: Path
    __api_version__: str = "memory/1.1"

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute(_CREATE_FACTS_TABLE)
            conn.execute(_CREATE_EPISODE_FACTS_TABLE)

    def supports(self, capability: str) -> bool:
        return capability in {"write_fact", "query", "episode_links", "long_term_memory"}

    def write_fact(self, fact: Fact) -> None:
        timestamp = (
            fact.metadata.get("started_at")
            or fact.metadata.get("timestamp")
            or datetime.now(timezone.utc).isoformat()
        )
        payload = (
            fact.id,
            fact.content,
            json.dumps(dict(fact.metadata), ensure_ascii=False),
            timestamp,
        )
        with self._connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO facts(id, content, metadata, created_at) VALUES (?, ?, ?, ?)",
                payload,
            )

    def query(self, query: MemoryQuery, *, k: int = 5) -> Sequence[Fact]:
        text = f"%{query.text.strip()}%" if query.text else "%"
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT id, content, metadata FROM facts WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                (text, k),
            )
            rows = cursor.fetchall()

        results: List[Fact] = []
        for fact_id, content, metadata_json in rows:
            metadata: Dict[str, Any] = json.loads(metadata_json)
            if _matches_filters(metadata, query.filters):
                results.append(Fact(id=fact_id, content=content, metadata=metadata))
        return results

    def link_episode(self, episode_id: str, fact_ids: Sequence[str]) -> None:
        if not fact_ids:
            return
        records: Iterable[tuple[str, str]] = ((episode_id, fact_id) for fact_id in fact_ids)
        with self._connection() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO episode_facts(episode_id, fact_id) VALUES (?, ?)",
                records,
            )

    def _connection(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path), detect_types=sqlite3.PARSE_DECLTYPES)


def _matches_filters(metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    if not filters:
        return True
    for key, expected in filters.items():
        value = metadata.get(key)
        if value != expected:
            return False
    return True
