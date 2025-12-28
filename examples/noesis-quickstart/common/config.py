from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from common.errors import ConfigError, NoesisApiError


def load_dotenv_if_present() -> None:
    """
    Minimal .env loader. Sets keys only if not already set in env.
    No external deps.
    """
    root = Path(__file__).resolve().parent.parent
    env_path = root / ".env"
    if not env_path.exists():
        return

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def require_openai_key() -> None:
    # Your runtime likely supports other providers, but this quickstart is explicit.
    if not os.getenv("OPENAI_API_KEY"):
        raise ConfigError(
            "Missing OPENAI_API_KEY.\n"
            "Fix:\n"
            "  1) cp .env.example .env\n"
            "  2) set OPENAI_API_KEY=... in .env\n"
            "  3) rerun"
        )


@dataclass(frozen=True)
class HelloConfig:
    seed: int = 0


def import_noesis() -> Any:
    try:
        import noesis as ns  # type: ignore
        return ns
    except Exception as e:
        raise NoesisApiError(
            "Could not import 'noesis'. Install it first.\n"
            "Fix: uv sync (or pip install noesis)\n"
            f"Import error: {e}"
        ) from e


def create_session(ns, *, governance_policy=None, planner_mode: str = "meta"):
    """
    Build a Noēsis Session with governance wired.

    - planner_mode="meta" is required if you want Governance + Insight phases.
    - governance_policy must implement `.evaluate(goal=..., plan=...)` returning GovernanceResult.
    """
    # Most Noēsis installs expose SessionBuilder here.
    try:
        from noesis.session import SessionBuilder  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Could not import noesis.session.SessionBuilder. "
            "Your Noēsis install/exports differ from the quickstart expectations."
        ) from e

    b = SessionBuilder.from_env()

    if hasattr(b, "with_planner_mode"):
        b = b.with_planner_mode(planner_mode)
    elif hasattr(b, "with_planner"):
        b = b.with_planner(planner_mode)
    else:
        pass

    # Attach governance if the builder supports it.
    if governance_policy is not None:
        if hasattr(b, "with_governance_policy"):
            b = b.with_governance_policy(governance_policy)
        elif hasattr(b, "with_governance"):
            b = b.with_governance(governance_policy)
        else:
            raise RuntimeError(
                "Could not attach governance policy. Your SessionBuilder doesn't expose a governance hook.\n"
                "Fix: update Noēsis or expose builder.with_governance_policy(...)."
            )

    return b.build()

def get_runs_dir(session: Any) -> Path:
    """
    SessionConfig exposes runs_dir via config_snapshot (per your models.py excerpt).
    """
    snap = getattr(session, "config_snapshot", None)
    if snap is None:
        raise NoesisApiError("Session missing config_snapshot.")
    runs_dir = getattr(snap, "runs_dir", None)
    if runs_dir is None:
        raise NoesisApiError("config_snapshot missing runs_dir.")
    return Path(runs_dir)