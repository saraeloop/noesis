"""
Deprecated wrapper for the split tutorials.

Use:
  - uv run python -m tutorials.langgraph_episode
  - uv run python -m tutorials.governed_side_effects
"""

from __future__ import annotations

from common.console import headline, info


def main() -> int:
    headline("Guarded LangGraph (deprecated)")
    info("This tutorial was split into two single-purpose demos:")
    info("  1) uv run python -m tutorials.langgraph_episode")
    info("  2) uv run python -m tutorials.governed_side_effects")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
