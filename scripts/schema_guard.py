"""Schema + KPI guard for ADR-003."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from ruamel.yaml import YAML

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_SRC_DIR = BASE_DIR / "internal_docs" / "schema"
MIG_SCHEMA_FILES = ["MIGRATIONS.schema.md", "MIGRATIONS.md"]
MIG_KPI_FILES = ["MIGRATIONS.kpi.md", "MIGRATIONS.md"]
PRIORITY = {5: 4, 4: 3, 3: 2, 2: 1}
_yaml = YAML(typ="safe")


@dataclass(frozen=True)
class SchemaGuardFinding:
    code: int
    file: str
    message: str
    details: Dict[str, Any]


def _run_git(args: List[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def _resolve_base_ref(explicit: Optional[str]) -> str:
    candidates = [explicit] if explicit else []
    candidates.extend(["origin/main", "main"])
    for candidate in candidates:
        if not candidate:
            continue
        result = _run_git(["merge-base", "HEAD", candidate], check=False)
        if result.returncode == 0:
            return result.stdout.strip()
    raise RuntimeError("Unable to resolve base reference for schema guard.")


def _list_changed_files(base: str) -> List[str]:
    result = _run_git(["diff", "--name-only", base, "HEAD"])
    paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return paths


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        data = _yaml.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected YAML structure in {path}")
    return data


def _load_yaml_from_git(rev: str, path: str) -> Optional[Dict[str, Any]]:
    result = _run_git(["show", f"{rev}:{path}"], check=False)
    if result.returncode != 0:
        return None
    data = _yaml.load(result.stdout)
    if not isinstance(data, dict):
        return None
    return data


def _extract_meta(data: Dict[str, Any]) -> Dict[str, Any]:
    section = data.get("schema")
    if not isinstance(section, dict):
        raise ValueError("schema block missing")
    return section


def _has_migration_touch(changed: Iterable[str], required_files: List[str]) -> bool:
    for candidate in required_files:
        if (BASE_DIR / candidate).exists() and candidate in changed:
            return True
    return False


def _compare_blocks(new_block: Any, old_block: Any) -> bool:
    return json.dumps(new_block, sort_keys=True, separators=(",", ":")) == json.dumps(old_block, sort_keys=True, separators=(",", ":"))


def _guard_generator() -> Optional[SchemaGuardFinding]:
    cmd = [sys.executable, str(BASE_DIR / "scripts" / "gen_schema.py"), "--check"]
    result = subprocess.run(cmd, cwd=BASE_DIR)
    if result.returncode == 0:
        return None
    if result.returncode == 2:
        return SchemaGuardFinding(
            code=5,
            file="docs/schema",
            message="Generated schema JSON is stale. Run `python scripts/gen_schema.py`.",
            details={"step": "canonical"},
        )
    return SchemaGuardFinding(
        code=5,
        file="docs/schema",
        message="Schema generator failed; inspect logs for details.",
        details={"step": "canonical", "returncode": result.returncode},
    )


def run_guard(base_ref: Optional[str] = None) -> List[SchemaGuardFinding]:
    generator_finding = _guard_generator()
    if generator_finding:
        return [generator_finding]

    base_sha = _resolve_base_ref(base_ref)
    changed_files = _list_changed_files(base_sha)
    findings: List[SchemaGuardFinding] = []

    for yaml_path in sorted(SCHEMA_SRC_DIR.glob("*.yaml")):
        rel = yaml_path.relative_to(BASE_DIR).as_posix()
        if rel not in changed_files:
            continue

        head_data = _load_yaml(yaml_path)
        base_data = _load_yaml_from_git(base_sha, rel)
        head_meta = _extract_meta(head_data)
        head_version = head_meta.get("version")
        schema_name = head_meta.get("name")

        old_version = None
        old_payload: Any = None
        new_payload: Any = None

        if "json_schema" in head_data:
            new_payload = head_data.get("json_schema")
        elif "kpis" in head_data:
            new_payload = head_data.get("kpis")
        else:
            continue

        if base_data:
            base_meta = _extract_meta(base_data)
            old_version = base_meta.get("version")
            old_payload = base_data.get("json_schema") if "json_schema" in base_data else base_data.get("kpis")

        if base_data is None:
            continue

        payload_changed = not _compare_blocks(new_payload, old_payload)
        version_changed = head_version != old_version

        if schema_name == "kpi" and payload_changed and not version_changed:
            findings.append(
                SchemaGuardFinding(
                    code=4,
                    file=rel,
                    message="KPI definitions changed without bumping schema version.",
                    details={"schema": schema_name, "version": head_version},
                )
            )
            continue

        if payload_changed and not version_changed:
            findings.append(
                SchemaGuardFinding(
                    code=2,
                    file=rel,
                    message="Schema changed without bumping $schema_version.",
                    details={"schema": schema_name, "version": head_version},
                )
            )
            continue

        if payload_changed and version_changed:
            required_files = MIG_KPI_FILES if schema_name == "kpi" else MIG_SCHEMA_FILES
            if not _has_migration_touch(changed_files, required_files):
                findings.append(
                    SchemaGuardFinding(
                        code=3,
                        file=rel,
                        message="Schema version bumped but no migration note found.",
                        details={"schema": schema_name, "from": old_version, "to": head_version},
                    )
                )

    return findings


def _emit_json(findings: List[SchemaGuardFinding], *, strict: bool) -> None:
    payload = {
        "status": "ok" if not findings else ("error" if strict else "warn"),
        "findings": [
            {
                "code": finding.code,
                "file": finding.file,
                "message": finding.message,
                "details": finding.details,
            }
            for finding in findings
        ],
    }
    print(json.dumps(payload, indent=2))


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate schema/KPI governance rules.")
    parser.add_argument("--base-ref", help="Git ref to diff against (defaults to origin/main).")
    parser.add_argument("--strict", action="store_true", help="Return non-zero when violations are detected.")
    parser.add_argument("--json", action="store_true", help="Emit findings as JSON for CI annotations.")
    args = parser.parse_args(argv)

    findings: List[SchemaGuardFinding] = []

    try:
        findings = run_guard(base_ref=args.base_ref)
    except Exception as e:
        # Always emit JSON on error when --json is set
        if args.json:
            error_finding = SchemaGuardFinding(
                code=5,
                file="scripts/schema_guard.py",
                message=f"Schema guard crashed: {type(e).__name__}: {str(e)}",
                details={"error": str(e), "type": type(e).__name__},
            )
            findings = [error_finding]
            _emit_json(findings, strict=args.strict)
        raise

    if args.json:
        _emit_json(findings, strict=args.strict)

    if not args.strict or not findings:
        return 0

    failing = max(findings, key=lambda item: PRIORITY.get(item.code, 0))
    return failing.code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
