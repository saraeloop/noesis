from __future__ import annotations

import argparse

from ..context import CLIContext
from ..render.base import OutputRenderer
from ..formatters import format_duration
from ..query import episode_status, status_label


class PsCommand:
    name = "ps"
    help = "Show a compact table of recent episodes"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--limit", type=int, default=20, help="Number of episodes to show (default: 20)")
        parser.add_argument("-j", "--json", action="store_true", help="JSON output")
        parser.add_argument("-q", "--quiet", action="store_true", help="Show episode ids only")
        parser.add_argument(
            "--strict-manifest",
            action="store_true",
            help="Re-hash manifests and warn when stored hashes drift",
        )

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        rows = ctx.ns.list_runs(
            limit=args.limit,
            context=ctx.runtime_context,
            strict_manifest=bool(args.strict_manifest),
        )
        ps_rows = []
        for row in rows:
            summary = {
                "status": row.get("status"),
                "flags": row.get("flags", {}) or {},
                "metrics": {
                    "success": row.get("success"),
                    "veto_count": row.get("veto_count"),
                },
            }
            status = episode_status(summary, None, None)
            label = status_label(status, governance_mode=summary["flags"].get("governance_mode"))
            episode_id = row.get("episode_id", "") or ""
            outcome = row.get("outcome")
            ps_rows.append(
                {
                    "episode_id": episode_id,
                    "episode_short": episode_id[:10],
                    "status": label,
                    "outcome": outcome,
                    "using": (row.get("flags", {}) or {}).get("using", "") or "",
                    "started_at": (row.get("started_at") or "")[:20],
                    "duration": format_duration(row.get("duration_sec")),
                }
            )

        if args.json:
            renderer.json(ps_rows)
            return 0
        renderer.print_ps(ps_rows, quiet=args.quiet)
        return 0


COMMAND = PsCommand()
