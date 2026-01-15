from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from noesis.domain.state.models import STATE_SCHEMA_VERSION, STATE_VERSION
from noesis.diagnostics import DriftResult, compare_runs
from noesis.interfaces.config import ConfigSnapshot
from noesis.runtime.config_provider import get_config_snapshot
from noesis.runtime.paths import resolve_noesis_paths
from noesis.runtime.artifacts.manifest import MANIFEST_FILE_NAME
from noesis.runtime.artifacts.verify import ManifestVerifier
from noesis.trace.schema import SUMMARY_SCHEMA_VERSION

from ..context import CLIContext
from ..render.base import OutputRenderer

SENSITIVE_KEYS = {"api_key", "token", "secret", "password", "auth", "bearer"}
_API_RE = re.compile(r"^[a-z][a-z0-9_-]*/\d+\.\d+(?:-[A-Za-z0-9.-]+)?$")


def _redact(payload: dict[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    for key, value in payload.items():
        lowered = key.lower()
        if any(token in lowered for token in SENSITIVE_KEYS):
            redacted[key] = "***redacted***"
        else:
            redacted[key] = value
    return redacted


@dataclass(slots=True)
class CheckResult:
    name: str
    status: Literal["ok", "warn", "error"]
    details: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "details": self.details}


class DiagnosticsCommand:
    name = "diagnostics"
    help = "Run stability diagnostics or replay comparison"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "mode",
            nargs="?",
            choices=["replay"],
            help="Optional subcommand: 'replay' compares two episode directories",
        )
        parser.add_argument("run_a", nargs="?", help="First episode directory (replay mode)")
        parser.add_argument("run_b", nargs="?", help="Second episode directory (replay mode)")
        parser.add_argument("-j", "--json", action="store_true", help="Emit JSON output")
        parser.add_argument("-q", "--quiet", action="store_true", help="Suppress human-readable output")
        parser.add_argument("--strict", action="store_true", help="Exit non-zero on warnings")
        parser.add_argument("--checks", help="Comma-separated list of checks to run")

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        if args.mode == "replay":
            return self._run_replay(args, renderer)
        snapshot = ctx.config_snapshot
        selected_checks = self._parse_checks(args.checks)
        port_map = ctx.runtime_context.list_ports()

        all_checks = list(self._run_checks(snapshot, port_map))
        checks = [check for check in all_checks if not selected_checks or check.name in selected_checks]

        missing = sorted(selected_checks - {check.name for check in all_checks})
        if missing:
            checks.append(
                CheckResult(
                    name="check_selection",
                    status="warn",
                    details=f"unknown checks requested: {', '.join(missing)}",
                )
            )

        overall = self._overall_status(checks)

        payload = {
            "timestamp": int(time.time()),
            "version": ctx.version,
            "summary_schema_version": SUMMARY_SCHEMA_VERSION,
            "state_version": STATE_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
            "config": _redact(snapshot.to_mapping()),
            "port_apis": port_map,
            "selected_checks": sorted(selected_checks) if selected_checks else ["all"],
            "checks": [check.to_dict() for check in checks],
            "status": overall,
        }

        if args.json:
            renderer.json(payload)
        elif not args.quiet:
            renderer.banner("Noēsis diagnostics")
            renderer.echo(f"timestamp             : {payload['timestamp']}")
            renderer.echo(f"version               : {ctx.version}")
            renderer.echo(f"summary_schema_version: {SUMMARY_SCHEMA_VERSION}")
            renderer.echo(f"state_version         : {STATE_VERSION} (schema {STATE_SCHEMA_VERSION})")
            renderer.echo(f"selected_checks       : {', '.join(payload['selected_checks'])}")
            renderer.echo("checks:")
            for check in checks:
                renderer.echo(f"  [{check.status}] {check.name} - {check.details}")
            renderer.echo(f"overall status        : {overall}")

        exit_code = 1 if (overall == "error" or (args.strict and overall == "warn")) else 0
        return exit_code

    def _run_checks(self, snapshot: ConfigSnapshot, ports: dict[str, str]) -> Iterable[CheckResult]:
        yield self._check_runs_dir(snapshot.runs_dir)
        yield self._check_learn_home(snapshot.learn_home)
        yield self._check_confidence_bounds("direction_min_confidence", snapshot.direction_min_confidence)
        yield self._check_confidence_bounds(
            "learn_auto_apply_min_confidence",
            snapshot.learn_auto_apply_min_confidence,
        )
        yield self._check_learn_successes(snapshot.learn_auto_apply_min_successes)
        yield self._check_ports(ports)
        yield self._check_config_snapshot(snapshot)
        yield self._check_latest_summary(snapshot.runs_dir)
        yield self._check_latest_manifest(snapshot.runs_dir)

    def _check_runs_dir(self, path: Path) -> CheckResult:
        layout = resolve_noesis_paths(workspace=None, runs_dir=path)
        expanded = layout.episodes_dir.expanduser()
        if not expanded.exists():
            return CheckResult("runs_dir", "warn", f"{expanded} (missing)")
        if not expanded.is_dir():
            return CheckResult("runs_dir", "error", f"{expanded} is not a directory")
        try:
            _, _, free = shutil.disk_usage(expanded)
        except Exception:
            free = None
        if not os.access(expanded, os.W_OK):
            return CheckResult("runs_dir", "warn", f"{expanded} not writable")
        if free is not None and free < 50 * 1024 * 1024:
            return CheckResult("runs_dir", "warn", f"{expanded} low free space ({free} bytes)")
        return CheckResult("runs_dir", "ok", str(expanded))

    def _check_learn_home(self, path: Path) -> CheckResult:
        expanded = path.expanduser()
        if not expanded.exists():
            return CheckResult("learn_home", "warn", f"{expanded} (missing)")
        if not expanded.is_dir():
            return CheckResult("learn_home", "error", f"{expanded} is not a directory")
        return CheckResult("learn_home", "ok", str(expanded))

    def _check_confidence_bounds(self, name: str, value: float) -> CheckResult:
        if 0.0 <= value <= 1.0:
            return CheckResult(name, "ok", f"{value:.2f}")
        return CheckResult(name, "error", f"{value} outside [0, 1]")

    def _check_learn_successes(self, value: int) -> CheckResult:
        if value < 1:
            return CheckResult(
                "learn_auto_apply_min_successes",
                "warn",
                f"expected >= 1, got {value}",
            )
        return CheckResult("learn_auto_apply_min_successes", "ok", str(value))

    def _check_ports(self, ports: dict[str, str]) -> CheckResult:
        if not ports:
            return CheckResult("ports", "warn", "no ports registered")

        status: Literal["ok", "warn"] = "ok"
        details: list[str] = []
        for name, api in sorted(ports.items()):
            label = f"{name}={api}"
            if not _API_RE.match(api):
                status = "warn"
                label += "(!)"
            details.append(label)
        return CheckResult("ports", status, ", ".join(details))

    def _check_config_snapshot(self, snapshot: ConfigSnapshot) -> CheckResult:
        runtime_mapping = get_config_snapshot().to_mapping()
        current_mapping = snapshot.to_mapping()
        if runtime_mapping == current_mapping:
            return CheckResult("config_snapshot", "ok", "in sync")
        return CheckResult(
            "config_snapshot",
            "warn",
            "runtime snapshot drift detected; consider reloading config",
        )

    def _check_latest_summary(self, runs_dir: Path) -> CheckResult:
        layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)
        roots = [path.expanduser() for path in layout.episode_roots()]
        if not any(path.exists() and path.is_dir() for path in roots):
            return CheckResult("latest_summary", "ok", "no runs directory")

        for base in roots:
            if not base.exists() or not base.is_dir():
                continue
            candidates = sorted((p for p in base.glob("ep_*") if p.is_dir()), reverse=True)
            for candidate in candidates:
                summary_path = candidate / "summary.json"
                if not summary_path.is_file():
                    continue
                try:
                    data = json.loads(summary_path.read_text(encoding="utf-8"))
                except Exception:
                    return CheckResult("latest_summary", "warn", f"{summary_path} unreadable")
                schema = data.get("schema_version")
                if schema == SUMMARY_SCHEMA_VERSION:
                    return CheckResult("latest_summary", "ok", f"{summary_path}")
                return CheckResult(
                    "latest_summary",
                    "warn",
                    f"{summary_path} schema_version={schema}",
                )
        return CheckResult("latest_summary", "ok", "no summary artifacts found")

    def _check_latest_manifest(self, runs_dir: Path) -> CheckResult:
        layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)
        roots = [path.expanduser() for path in layout.episode_roots()]
        if not any(path.exists() and path.is_dir() for path in roots):
            return CheckResult("artifact_manifest", "ok", "no runs directory")
        for base in roots:
            if not base.exists() or not base.is_dir():
                continue
            candidates = sorted((p for p in base.glob("ep_*") if p.is_dir()), reverse=True)
            for candidate in candidates:
                manifest_path = candidate / MANIFEST_FILE_NAME
                if not manifest_path.is_file():
                    continue
                try:
                    verifier = ManifestVerifier(run_dir=candidate)
                    report = verifier.verify_path(manifest_path)
                except Exception:
                    return CheckResult("artifact_manifest", "warn", f"{manifest_path} unreadable")
                if report.status == "ok":
                    return CheckResult("artifact_manifest", "ok", f"{manifest_path}")
                issue = report.issues[0] if report.issues else None
                detail = issue.detail if issue else "verification failed"
                return CheckResult("artifact_manifest", "error", f"{manifest_path}: {detail}")
        return CheckResult("artifact_manifest", "warn", "no manifest found")

    def _run_replay(self, args: argparse.Namespace, renderer: OutputRenderer) -> int:
        run_a = args.run_a
        run_b = args.run_b
        if not run_a or not run_b:
            renderer.echo("usage: noesis diagnostics replay <run_a_dir> <run_b_dir>")
            return 2
        result = compare_runs(Path(run_a), Path(run_b))
        if args.json:
            payload = {
                "status": result.status,
                "mismatches": [{"artifact": m.artifact, "detail": m.detail} for m in result.mismatches],
            }
            renderer.json(payload)
        elif not args.quiet:
            if result.is_drift:
                renderer.echo("DRIFT detected:")
                for mismatch in result.mismatches:
                    renderer.echo(f"- {mismatch.artifact}: {mismatch.detail}")
            else:
                renderer.echo("NO DRIFT")
        return 1 if result.is_drift else 0

    @staticmethod
    def _overall_status(checks: Iterable[CheckResult]) -> Literal["ok", "warn", "error"]:
        seen_error = False
        seen_warn = False
        for check in checks:
            if check.status == "error":
                seen_error = True
                break
            if check.status == "warn":
                seen_warn = True
        if seen_error:
            return "error"
        if seen_warn:
            return "warn"
        return "ok"

    @staticmethod
    def _parse_checks(raw: str | None) -> set[str]:
        if not raw:
            return set()
        return {token.strip() for token in raw.split(",") if token.strip()}


COMMAND = DiagnosticsCommand()
