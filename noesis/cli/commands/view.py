from __future__ import annotations

import argparse
from pathlib import Path

from ..context import CLIContext
from ..render.base import OutputRenderer
from ..errors import EXIT_ERROR
from ..query import load_episode_dir, iter_events
from ..view_models import build_episode_dashboard, build_episode_dashboard_from_payloads


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
        parser.add_argument("--limit", type=int, default=50, help="Limit timeline rows (default: 50)")
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

    def _emit_validation(self, renderer: OutputRenderer, issues: list[str]) -> None:
        if not issues:
            return
        renderer.banner("validation issues")
        for issue in issues:
            renderer.echo(f"! {issue}")

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        schema_override = self._schema_override(getattr(args, "schema", None))
        target = Path(args.target).expanduser()
        if target.exists():
            ep_dir = target if target.is_dir() else target.parent
            use_remote = False
        else:
            ep_dir = load_episode_dir(args.target, ctx.config_snapshot.runs_dir)
            use_remote = not ep_dir.exists()

        if args.open:
            renderer.banner("artifacts")
            renderer.echo(f"dir: {ep_dir}")
            renderer.echo(f"summary: {ep_dir / 'summary.json'}")
            renderer.echo(f"events: {ep_dir / 'events.jsonl'}")

        mode = "pretty"
        vm = None
        if args.json:
            mode = "json"
            if use_remote:
                summary, events = self._load_remote(args.target, ctx)
                vm = build_episode_dashboard_from_payloads(
                    summary=summary,
                    events=events,
                    episode_id=args.target,
                    limit_timeline=args.limit,
                    validate=True,
                    schema_override=schema_override,
                )
            else:
                vm = build_episode_dashboard(
                    ep_dir,
                    limit_timeline=args.limit,
                    validate=True,
                    schema_override=schema_override,
                )
            renderer.json(vm.to_dict())
        elif args.events:
            mode = "events"
            if use_remote:
                renderer.print_events(ctx.ns.events.read(args.target, context=ctx.runtime_context, stream=True))
            else:
                renderer.print_events(iter_events(ep_dir))
        else:
            mode = "pretty"
            grep = getattr(args, "grep", None)
            if use_remote:
                summary, events = self._load_remote(args.target, ctx)
                vm = build_episode_dashboard_from_payloads(
                    summary=summary,
                    events=events,
                    episode_id=args.target,
                    limit_timeline=args.limit,
                    validate=bool(args.fail_on_invalid or ctx.options.debug or ctx.options.verbose),
                    schema_override=schema_override,
                )
            else:
                vm = build_episode_dashboard(
                    ep_dir,
                    limit_timeline=args.limit,
                    validate=bool(args.fail_on_invalid or ctx.options.debug or ctx.options.verbose),
                    schema_override=schema_override,
                )
            renderer.print_viewer(vm, grep=grep)
            if ctx.options.debug or ctx.options.verbose:
                self._emit_validation(renderer, vm.validation_issues)

        if args.fail_on_invalid:
            if vm is None:
                if use_remote:
                    summary, events = self._load_remote(args.target, ctx)
                    vm = build_episode_dashboard_from_payloads(
                        summary=summary,
                        events=events,
                        episode_id=args.target,
                        limit_timeline=args.limit,
                        validate=True,
                        schema_override=schema_override,
                    )
                else:
                    vm = build_episode_dashboard(
                        ep_dir,
                        limit_timeline=args.limit,
                        validate=True,
                        schema_override=schema_override,
                    )
            if vm.validation_issues:
                if mode != "pretty":
                    self._emit_validation(renderer, vm.validation_issues)
                return EXIT_ERROR
        return 0

    def _load_remote(self, episode_id: str, ctx: CLIContext) -> tuple[dict, list[dict]]:
        try:
            summary = ctx.ns.summary.read(episode_id, context=ctx.runtime_context)
            events = list(ctx.ns.events.read(episode_id, context=ctx.runtime_context))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"episode {episode_id} not found") from exc
        return summary, events


COMMAND = ViewCommand()
