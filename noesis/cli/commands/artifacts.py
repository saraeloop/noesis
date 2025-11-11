from __future__ import annotations

import argparse
from pathlib import Path

from noesis.runtime.artifacts.manifest import MANIFEST_FILE_NAME
from noesis.runtime.artifacts.verify import ManifestVerifier

from ..context import CLIContext
from ..render.base import OutputRenderer

EXIT_OK = 0
EXIT_VERIFY_ERROR = 2
EXIT_MISSING = 3
EXIT_SIGNATURE = 4


class ArtifactsCommand:
    name = "artifacts"
    help = "Artifact manifest utilities"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        subcommands = parser.add_subparsers(dest="artifacts_action")

        verify = subcommands.add_parser("verify", help="Verify an episode manifest")
        verify.add_argument(
            "target",
            help="Episode ID, run directory, or explicit manifest path",
        )
        verify.add_argument(
            "--strict",
            action="store_true",
            help="Fail when unexpected files are present",
        )
        verify.add_argument(
            "--json",
            action="store_true",
            help="Emit JSON output instead of human-readable text",
        )
        verify.add_argument(
            "-q",
            "--quiet",
            action="store_true",
            help="Suppress human-readable output",
        )

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        action = getattr(args, "artifacts_action", None)
        if action == "verify":
            return self._run_verify(args, ctx, renderer)
        raise ValueError("artifacts command requires a subcommand (e.g. 'verify')")

    def _run_verify(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        try:
            manifest_path = self._resolve_manifest_path(args.target, ctx)
        except FileNotFoundError as err:
            if not args.quiet:
                renderer.echo(f"error: {err}")
            return EXIT_MISSING

        verifier = ManifestVerifier(run_dir=manifest_path.parent, strict=bool(args.strict))
        report = verifier.verify_path(manifest_path)

        if args.json:
            renderer.json(report.to_dict())
        elif not args.quiet:
            renderer.banner("Artifact verification")
            renderer.echo(f"manifest : {manifest_path}")
            renderer.echo(f"status   : {report.status}")
            renderer.echo(f"files    : {report.files_checked}")
            renderer.echo(f"duration : {report.duration_ms:.2f} ms")
            if report.issues:
                renderer.echo("issues   :")
                for issue in report.issues:
                    renderer.echo(f"  - [{issue.kind}] {issue.name}: {issue.detail}")
            else:
                renderer.echo("issues   : none")
            renderer.echo("files detail:")
            for file in report.files:
                detail = []
                if file.expected_sha256 and file.actual_sha256 and file.expected_sha256 != file.actual_sha256:
                    detail.append("sha mismatch")
                if file.expected_size is not None and file.actual_size is not None and file.expected_size != file.actual_size:
                    detail.append("size mismatch")
                suffix = f" ({', '.join(detail)})" if detail else ""
                renderer.echo(f"  - {file.name}: {file.status}{suffix}")

        return self._exit_code(report)

    def _resolve_manifest_path(self, target: str, ctx: CLIContext) -> Path:
        candidate = Path(target).expanduser()
        if candidate.is_file():
            return candidate
        if candidate.is_dir():
            manifest = candidate / MANIFEST_FILE_NAME
            if manifest.is_file():
                return manifest
        runs_dir = ctx.config_snapshot.runs_dir
        episode_dir = runs_dir / target
        if episode_dir.is_dir():
            manifest = episode_dir / MANIFEST_FILE_NAME
            if manifest.is_file():
                return manifest
        manifest = runs_dir / target
        if manifest.is_file():
            return manifest
        raise FileNotFoundError(f"Could not locate manifest for target '{target}'")

    @staticmethod
    def _exit_code(report) -> int:
        if report.status == "ok" or report.status == "warn":
            if report.status == "warn":
                # Warns (e.g. unexpected files) should not fail verification.
                return EXIT_OK
            return EXIT_OK
        if any(issue.kind == "signature" for issue in report.issues):
            return EXIT_SIGNATURE
        if any(issue.kind == "missing" for issue in report.issues):
            return EXIT_MISSING
        return EXIT_VERIFY_ERROR


COMMAND = ArtifactsCommand()
