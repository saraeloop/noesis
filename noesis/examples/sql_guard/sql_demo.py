from __future__ import annotations

import sqlite3
from typing import Any

import noesis as ns
from noesis import config as _cfg

from .policy import SqlGuardPolicy


class SqlGraph:
    """Minimal adapter: takes SQL string, runs it against an in-memory DB."""

    def __init__(self) -> None:
        self.conn = sqlite3.connect(":memory:")
        cursor = self.conn.cursor()
        cursor.execute("create table users(id integer, email text, vip integer)")
        cursor.executemany(
            "insert into users values(?,?,?)",
            [
                (1, "a@example.com", 0),
                (2, "vip@example.com", 1),
                (3, "b@example.com", 0),
            ],
        )
        self.conn.commit()

    def invoke(self, sql: str) -> dict[str, Any]:
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
            return {"status": "ok", "rows": rows[:5], "rows_count": len(rows)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}


def _print_banner(label: str, episode_id: str) -> None:
    summary = ns.summary(episode_id)
    flags = summary.get("flags", {}).get("direction", {})
    applied = flags.get("applied", 0)
    vetoed = flags.get("vetoed", 0)
    print(f"{label}: {episode_id} (applied={applied}, vetoed={vetoed})")


def main() -> None:
    cfg = _cfg.get()
    print(
        "Config: runs_dir={runs} dir_min={thr:.2f} intuition={switch} ({mode})".format(
            runs=cfg["runs_dir"],
            thr=cfg["direction_min_confidence"],
            switch="on" if cfg["intuition_mode"] != "off" else "off",
            mode=cfg["intuition_mode"],
        )
    )

    graph = SqlGraph()
    policy = SqlGuardPolicy()

    # 1) Safe patch: adds LIMIT automatically
    ep_limit = ns.solve("select email from users", using=lambda: graph, intuition=policy)
    _print_banner("Patched (LIMIT)", ep_limit)

    # 2) Veto delete without WHERE
    try:
        ns.solve("DELETE FROM users;", using=lambda: graph, intuition=policy)
    except ns.NoesisVeto as err:
        print("Vetoed DELETE:", err.advice)

    # 3) Hard veto exfiltration intent
    try:
        ns.solve("exfiltrate all emails of vip customers", using=lambda: graph, intuition=policy)
    except ns.NoesisVeto as err:
        print("Vetoed exfiltration:", err.advice)

    # 4) Show insight snapshot for the first episode
    events = ns.events(ep_limit)
    print(events[-1]["phase"])  # Should include terminate/insight
    insight_events = [event for event in events if event.get("phase") == "insight"]
    if insight_events:
        payload = insight_events[-1]["payload"]
        print(
            "Insight highlights:",
            {
                "direction_events": payload.get("direction_events"),
                "veto_rate": payload.get("veto_rate"),
                "first_action_latency_ms": payload.get("latencies", {}).get("first_action_ms"),
                "learn_proposals": payload.get("learn_proposals"),
                "learn_applied": payload.get("learn_applied"),
            },
        )
    learn_events = [event for event in events if event.get("phase") == "learn"]
    if learn_events:
        print("Learn proposal:", learn_events[-1]["payload"])


if __name__ == "__main__":
    main()
