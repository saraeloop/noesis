from __future__ import annotations

import asyncio
from pathlib import Path

import noesis as ns


def _configure(tmp_path: Path) -> dict[str, object]:
    runs_dir = tmp_path / "runs"
    learn_dir = tmp_path / "learn"
    original = ns.get()
    ns.set(
        runs_dir=str(runs_dir),
        learn_home=str(learn_dir),
        planner_mode="minimal",
        governance_mode="off",
    )
    return original


def _restore(original: dict[str, object]) -> None:
    ns.set(
        runs_dir=original["runs_dir"],
        learn_home=original["learn_home"],
        planner_mode=original.get("planner_mode", "meta"),
        governance_mode=original.get("governance_mode", "off"),
    )


def test_solve_async_with_async_callable(tmp_path: Path) -> None:
    original = _configure(tmp_path)

    async def async_adapter(task: str) -> dict[str, object]:
        return {"result": task}

    async def run() -> str:
        return await ns.solve_async("async task", using=async_adapter, intuition=False)

    episode_id = asyncio.run(run())
    summary = ns.summary.read(episode_id)

    assert summary["metrics"]["success"] == 1

    _restore(original)


def test_solve_async_with_sync_callable(tmp_path: Path) -> None:
    original = _configure(tmp_path)

    def sync_adapter(task: str) -> dict[str, object]:
        return {"result": task}

    async def run() -> str:
        return await ns.solve_async("sync task", using=sync_adapter, intuition=False)

    episode_id = asyncio.run(run())
    summary = ns.summary.read(episode_id)

    assert summary["metrics"]["success"] == 1

    _restore(original)


def test_solve_async_invocation_precedence(tmp_path: Path) -> None:
    original = _configure(tmp_path)

    class AsyncInvokeRun:
        def __init__(self) -> None:
            self.called: list[str] = []

        async def invoke(self, payload: object) -> dict[str, object]:
            self.called.append("invoke")
            return {"result": payload}

        async def run(self, payload: object) -> dict[str, object]:
            self.called.append("run")
            return {"result": payload}

        async def __call__(self, payload: object) -> dict[str, object]:
            self.called.append("call")
            return {"result": payload}

    adapter = AsyncInvokeRun()

    async def run() -> str:
        return await ns.solve_async("precedence task", using=adapter, intuition=False)

    asyncio.run(run())

    assert adapter.called[0] == "invoke"

    _restore(original)


def test_solve_async_records_adapter_error(tmp_path: Path) -> None:
    original = _configure(tmp_path)

    async def failing_adapter(task: str) -> dict[str, object]:
        raise RuntimeError("boom")

    async def run() -> str:
        return await ns.solve_async("bad task", using=failing_adapter, intuition=False)

    episode_id = asyncio.run(run())
    summary = ns.summary.read(episode_id)
    assert summary["metrics"]["success"] == 0

    events = list(ns.events.read(episode_id))
    reflect_event = next(e for e in events if e["phase"] == "reflect")
    reasons = reflect_event["payload"].get("reasons", [])
    assert "adapter_error" in reasons

    _restore(original)
