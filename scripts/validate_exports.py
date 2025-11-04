#!/usr/bin/env python3
"""Dry-run scaffold for validating documented exports against runtime modules."""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Iterable, Set

LOG = logging.getLogger("validate_exports")

INTERNAL_MODULES = {
    "__pycache__",
    "adapters",
    "cli",
    "cli.py",
    "config",
    "core",
    "deprecated",
    "direction",
    "domain",
    "exceptions",
    "infrastructure",
    "interfaces",
    "intuition",
    "loader",
    "state",
    "tools",
    "usecases",
}

RUNTIME_ALLOWED = {"events", "summary", "learning", "utils"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate documented exports match the runtime surface."
    )
    parser.add_argument(
        "--package",
        default="noesis",
        help="Top-level package to inspect (default: %(default)s).",
    )
    parser.add_argument(
        "--package-root",
        default="noesis",
        help="Path to the package root relative to the repo (default: %(default)s).",
    )
    parser.add_argument(
        "--docs-root",
        default="docs/app/reference",
        help="Path to the reference docs describing exports (default: %(default)s).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail the command if mismatches are detected.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def iter_doc_files(root: Path) -> Iterable[Path]:
    return sorted(root.rglob("*.mdx"))


def load_documented_exports(root: Path) -> Set[str]:
    """Extract documented exports from the reference docs."""
    documented: Set[str] = set()
    if not root.exists():
        LOG.warning("Reference documentation %s not found; returning no exports.", root)
        return documented

    pattern = re.compile(r"`(noesis[\w\.]+)`")
    for doc in iter_doc_files(root):
        text = doc.read_text(encoding="utf-8")
        for match in pattern.findall(text):
            candidate = match.strip()
            if "*" in candidate or " " in candidate:
                continue
            if _is_supported_module(candidate):
                documented.add(candidate)
    return documented


def _is_supported_module(name: str) -> bool:
    parts = name.split(".")
    if not parts or parts[0] != "noesis":
        return False
    if len(parts) == 1:
        return True
    if len(parts) == 2:
        return parts[1].islower()
    if len(parts) == 3 and parts[1] == "runtime":
        return parts[2] in RUNTIME_ALLOWED
    return False


def _module_exists(package_root: Path, module: str) -> bool:
    parts = module.split(".")[1:]  # drop top-level package name
    current = package_root
    if not parts:
        return package_root.exists()

    for part in parts:
        module_file = current / f"{part}.py"
        package_dir = current / part
        if module_file.exists():
            current = module_file
            continue
        if package_dir.exists() and (package_dir / "__init__.py").exists():
            current = package_dir
            continue
        return False
    return True


def load_runtime_exports(package_root: Path, package: str) -> Set[str]:
    """Inspect runtime modules considered public."""
    exports: Set[str] = set()
    if not package_root.exists():
        LOG.warning("Package root %s not found; returning no exports.", package_root)
        return exports

    if _module_exists(package_root, package):
        exports.add(package)

    for child in sorted(package_root.iterdir()):
        name = child.stem if child.is_file() else child.name
        if name.startswith("_") or name in INTERNAL_MODULES:
            continue
        if child.is_file() and child.suffix != ".py":
            continue
        if child.is_dir() and not (child / "__init__.py").exists():
            continue

        if name == "runtime":
            for sub in sorted(child.iterdir()):
                sub_name = sub.stem if sub.is_file() else sub.name
                if sub_name.startswith("_") or sub_name not in RUNTIME_ALLOWED:
                    continue
                module = f"{package}.runtime.{sub_name}"
                if _module_exists(package_root, module):
                    exports.add(module)
            continue

        module_name = f"{package}.{name}"
        if _module_exists(package_root, module_name):
            exports.add(module_name)

    return exports


def render_diff(
    documented: Iterable[str], runtime: Iterable[str]
) -> tuple[Set[str], Set[str]]:
    documented_set = set(documented)
    runtime_set = set(runtime)
    missing = runtime_set - documented_set
    undocumented = documented_set - runtime_set
    return missing, undocumented


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    docs_root = Path(args.docs_root)
    package_root = Path(args.package_root)

    documented = load_documented_exports(docs_root)
    if args.package:
        documented.add(args.package)
    runtime = load_runtime_exports(package_root, args.package)

    missing, undocumented = render_diff(documented, runtime)

    if missing:
        LOG.warning("Exports missing from docs: %s", ", ".join(sorted(missing)))
    if undocumented:
        LOG.warning("Docs mention exports not present at runtime: %s", ", ".join(sorted(undocumented)))

    if not documented and not runtime:
        LOG.info("No exports collected (expected while the scaffold is incomplete).")

    if args.strict and (missing or undocumented):
        LOG.error("Strict mode active; export mismatches detected.")
        return 1

    LOG.info("validate_exports completed (dry-run).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
