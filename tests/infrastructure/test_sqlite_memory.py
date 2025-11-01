from __future__ import annotations

from pathlib import Path

from noesis.infrastructure.memory.sqlite import SQLiteMemory
from noesis.interfaces.memory import Fact, MemoryQuery


def test_sqlite_memory_persists_and_queries(tmp_path):
    adapter = SQLiteMemory(db_path=tmp_path / "memory.db")
    fact = Fact(
        id="episode:ep_1",
        content="Summarize quarterly report",
        metadata={"episode_id": "ep_1", "task": "Summarize quarterly report"},
    )

    adapter.write_fact(fact)
    adapter.link_episode("ep_1", [fact.id])

    results = adapter.query(MemoryQuery(text="quarterly"))
    assert results
    assert results[0].id == fact.id
    assert results[0].metadata["episode_id"] == "ep_1"
    assert adapter.supports("long_term_memory")


def test_sqlite_memory_filters_results(tmp_path):
    adapter = SQLiteMemory(db_path=tmp_path / "memory.db")
    fact_a = Fact(
        id="episode:a",
        content="Alpha task",
        metadata={"episode_id": "a", "project": "alpha"},
    )
    fact_b = Fact(
        id="episode:b",
        content="Beta task",
        metadata={"episode_id": "b", "project": "beta"},
    )
    adapter.write_fact(fact_a)
    adapter.write_fact(fact_b)

    results = adapter.query(MemoryQuery(text="", filters={"project": "beta"}))
    assert len(results) == 1
    assert results[0].id == fact_b.id
