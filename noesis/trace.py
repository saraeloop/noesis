"""
Tracing contracts: events.jsonl (append-only) and summary.json (single file).

Only defines interfaces & helpers; real IO lives in runner.
"""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Iterator, List, Any
import json

EVENTS_FILE = "events.jsonl"
SUMMARY_FILE = "summary.json"

def write_event(dir_path: Path, event: Dict[str, Any]) -> None:
    """Append a single JSON event line (caller ensures schema)."""
    dir_path.mkdir(parents=True, exist_ok=True)
    with (dir_path / EVENTS_FILE).open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def iter_events(dir_path: Path) -> Iterator[Dict[str, Any]]:
    """Yield events from events.jsonl if present."""
    p = dir_path / EVENTS_FILE
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def read_events(dir_path: Path) -> List[Dict[str, Any]]:
    return list(iter_events(dir_path))

def write_summary(dir_path: Path, summary: Dict[str, Any]) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    with (dir_path / SUMMARY_FILE).open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

def read_summary(dir_path: Path) -> Dict[str, Any]:
    with (dir_path / SUMMARY_FILE).open("r", encoding="utf-8") as f:
        return json.load(f)