"""
Noēsis — a framework for intuition-guided agentic reasoning.

Public API surface (stable):
    run(task, *, seed=0, intuition=True, tags=None) -> str
    summary(episode_id) -> dict
    events(episode_id, *, stream=False) -> list[dict] | Iterator[dict]
    metrics(episode_id) -> dict
    list(limit=50, since=None) -> list[dict]
    last() -> str | None
    set(**overrides) -> None
    paths(episode_id) -> dict
"""
from .runner import run, summary, events, metrics, list, last, set, paths 