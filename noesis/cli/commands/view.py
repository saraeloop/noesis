from __future__ import annotations

import argparse

from ..context import CLIContext
from ..render.base import OutputRenderer
from ..errors import EXIT_ERROR
from ..viewer import load_episode_view


class ViewCommand:
    name = "view"
    help = "Inspect an episode timeline, metrics, and governance decisions"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("target", help="Episode ID or run directory")
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--pretty", action="store_true", help="Render formatted tables (default)")
        group.add_argument("-j", "--json", action="store_true", help="Emit JSON view")
        group.add_argument("--events", action="store_true", help="Stream raw events.jsonl")
        parser.add_argument("--grep", help="Filter timeline rows by substring (e.g. 'phase=governance')")
        parser.add_argument("--schema", default="latest", help="Summary schema to validate against (default: auto)")
        parser.add_argument(
            "--fail-on-invalid",
            action="store_true",
            help="Exit with status 1 if validation errors are detected",
        )
        parser.add_argument(
            "--open",
            action="store_true",
            help="Print artifact paths (useful for hand inspection or dashboards)",
        )

    def _schema_override(self, raw: str | None) -> str | None:
        if not raw:
            return None
        value = raw.strip().lower()
        if value in {"", "latest", "auto"}:
            return None
        return raw

    def _emit_validation(self, renderer: OutputRenderer, view, *, already_rendered: bool) -> None:
        if not view.validation:
            return
        if already_rendered:
            return  # pretty renderer already printed validation
        renderer.banner("validation issues")
        for issue in view.validation:
            renderer.echo(f"! {issue.format()}")

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        schema_override = self._schema_override(getattr(args, "schema", None))
        view = load_episode_view(
            args.target,
            ns=ctx.ns,
            runtime_context=ctx.runtime_context,
            schema_override=schema_override,
            debug=ctx.options.debug or ctx.options.verbose,
        )

        if args.open and view.paths:
            renderer.banner("artifacts")
            for key in ("dir", "summary", "events"):
                path = view.paths.get(key)
                if path:
                    renderer.echo(f"{key}: {path}")

        mode = "pretty"
        if args.json:
            mode = "json"
            renderer.json(view.to_dict())
        elif args.events:
            mode = "events"
            renderer.print_events(view.events)
        else:
            mode = "pretty"
            grep = getattr(args, "grep", None)
            renderer.print_viewer(view, grep=grep)

        self._emit_validation(renderer, view, already_rendered=(mode == "pretty"))
        if args.fail_on_invalid and view.invalid:
            return EXIT_ERROR
        return 0


COMMAND = ViewCommand()
