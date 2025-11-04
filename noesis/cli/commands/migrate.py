from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, TYPE_CHECKING

from ..context import CLIContext
from ..render.base import OutputRenderer
from ..errors import EXIT_ERROR

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ...tools.migrate import MigrationReport


class MigrateCommand:
    name = "migrate"
    help = "Codemod deprecated shims to the modern Noēsis API"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "paths",
            nargs="*",
            default=["."],
            help="Files or directories to migrate (defaults to current directory)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without modifying files",
        )
        parser.add_argument(
            "-j",
            "--json",
            action="store_true",
            help="Emit JSON report instead of human-readable output",
        )

    def _json_report(self, renderer: OutputRenderer, report: "MigrationReport") -> None:
        renderer.json(report.to_dict())

    def _human_report(self, renderer: OutputRenderer, report: "MigrationReport") -> None:
        renderer.banner("codemod summary")
        renderer.echo(f"  renamed : {report.renamed}")
        renderer.echo(f"  replaced: {report.replaced}")
        renderer.echo(f"  skipped : {report.skipped}")
        if report.errors:
            renderer.echo("")
            renderer.echo("errors:")
            for err in report.errors:
                renderer.echo(f"  - {err}")
        if report.todo:
            renderer.echo("")
            renderer.echo("TODO:")
            for path, symbols in report.todo_items():
                joined = ", ".join(sorted(symbols))
                renderer.echo(f"  - {path}: {joined}")

    @staticmethod
    def _exit_code(report: "MigrationReport") -> int:
        if report.errors:
            return EXIT_ERROR
        if report.todo or report.skipped:
            return 2
        return 0

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        try:
            from ...tools.migrate import run_migration
        except RuntimeError as exc:
            renderer.echo(str(exc))
            return EXIT_ERROR
        except ImportError as exc:  # pragma: no cover - defensive
            renderer.echo(
                "Failed to load migration tooling. Install the optional dependencies with "
                "`pip install noesis[migrate]`."
            )
            renderer.echo(str(exc))
            return EXIT_ERROR

        raw_paths: Iterable[str] = args.paths or ["."]
        path_objects: List[Path] = [Path(p).resolve() for p in raw_paths]
        report = run_migration(path_objects, apply=not args.dry_run)
        if args.json:
            self._json_report(renderer, report)
        else:
            self._human_report(renderer, report)
        return self._exit_code(report)


COMMAND = MigrateCommand()
