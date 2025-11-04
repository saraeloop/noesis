#!/usr/bin/env python3
"""Aggregated pre-release checks with dry-run execution."""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

LOG = logging.getLogger("pre_release")


@dataclass
class Check:
    name: str
    command: List[str]
    description: str
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None


CHECKS: List[Check] = [
    Check(
        name="unit-tests",
        command=["uv", "run", "python", "-m", "pytest"],
        description="Execute the full Python test suite.",
    ),
    Check(
        name="diagnostics-help",
        command=["uv", "run", "noesis", "diagnostics", "--help"],
        description="Ensure diagnostics CLI wiring is available.",
    ),
    Check(
        name="validate-ports",
        command=["uv", "run", "noesis", "validate-ports", "--json"],
        description="Snapshot declared port APIs via CLI.",
    ),
    Check(
        name="cli-smoke",
        command=["uv", "run", "noesis", "--help"],
        description="Verify the root CLI entry point imports cleanly.",
    ),
    Check(
        name="validate-exports",
        command=["uv", "run", "scripts/validate_exports.py", "--strict"],
        description="Ensure documented exports match the public surface.",
    ),
    Check(
        name="docs-build",
        command=["pnpm", "run", "build"],
        description="Build docs site to catch broken links and compilation issues.",
        cwd="docs",
    ),
    Check(
        name="telemetry-smoke",
        command=[
            "uv",
            "run",
            "python",
            "-c",
            (
                "import os; "
                "os.environ.setdefault('NOESIS_OTLP_URL', 'http://127.0.0.1:4317'); "
                "import noesis; "
                "print('telemetry smoke ok')"
            ),
        ],
        description="Import with telemetry endpoint set to confirm safe fallback.",
    ),
    Check(
        name="build-wheel",
        command=["uv", "build"],
        description="Build distribution artifacts to confirm packaging health.",
    ),
]

SUMMARY_DIR = Path(".noesis/prerelease")
SUMMARY_PATH = SUMMARY_DIR / "summary.txt"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Noēsis pre-release checks (supports dry-run)."
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Run all predefined checks in order.",
    )
    parser.add_argument(
        "--checks",
        nargs="+",
        metavar="NAME",
        help="Run a subset of checks by name.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute commands instead of logging a dry-run.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available checks and exit.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def resolve_checks(selected: Iterable[str] | None) -> List[Check]:
    if not selected:
        return CHECKS

    index = {check.name: check for check in CHECKS}
    unknown = [name for name in selected if name not in index]
    if unknown:
        raise KeyError(f"Unknown check(s): {', '.join(unknown)}")
    return [index[name] for name in selected]


def run_check(check: Check, execute: bool) -> bool:
    LOG.info("Running check: %s - %s", check.name, check.description)
    if not execute:
        LOG.info("DRY-RUN: %s", " ".join(check.command))
        return True

    try:
        env = None
        if check.env:
            env = {**os.environ, **check.env}
        subprocess.run(check.command, check=True, env=env, cwd=check.cwd)
        return True
    except subprocess.CalledProcessError as exc:
        LOG.error("Check %s failed with exit code %s", check.name, exc.returncode)
        return False


def list_checks() -> None:
    for check in CHECKS:
        LOG.info(
            "%s: %s -> %s",
            check.name,
            " ".join(check.command),
            check.description,
        )


def write_summary(
    results: List[tuple[Check, bool]], executed: bool, failures: int
) -> None:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    mode = "executed" if executed else "dry-run"
    lines = [
        "Noēsis pre-release summary",
        f"mode: {mode}",
        f"checks: {len(results)}",
        f"failures: {failures}",
        "",
        "check\tstatus\tcommand",
    ]
    for check, success in results:
        status = "ok" if success else "fail"
        lines.append(f"{check.name}\t{status}\t{' '.join(check.command)}")

    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if args.list:
        list_checks()
        return 0

    selected_names = None
    if args.checks:
        selected_names = args.checks
    elif not args.check_all:
        parser.error("Specify --check-all or provide --checks NAME [NAME ...].")

    try:
        checks = resolve_checks(selected_names)
    except KeyError as error:
        parser.error(str(error))

    failures = 0
    results: List[tuple[Check, bool]] = []
    for check in checks:
        success = run_check(check, execute=args.execute)
        results.append((check, success))
        if not success:
            failures += 1

    write_summary(results, args.execute, failures)

    if failures:
        LOG.error("%s check(s) failed.", failures)
        return 1

    mode = "executed" if args.execute else "dry-run"
    LOG.info("All checks %s successfully.", mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
