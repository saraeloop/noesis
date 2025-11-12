"""Schema generator for ADR-003.

Reads YAML definitions from ``internal_docs/schema`` and emits canonical,
versioned JSON schemas plus reference docs under ``docs/schema``.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from ruamel.yaml import YAML

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_SRC_DIR = BASE_DIR / "internal_docs" / "schema"
SCHEMA_OUT_DIR = BASE_DIR / "docs" / "schema"
REFERENCE_DOC = BASE_DIR / "docs" / "app" / "reference" / "schema-index.mdx"
MANIFEST_PATH = SCHEMA_OUT_DIR / "MANIFEST.json"
SCHEMA_BASE_URL = "https://schemas.noesis.dev"
JSON_SCHEMA_URL = "https://json-schema.org/draft/2020-12/schema"
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")

_yaml = YAML(typ="safe")


@dataclass(frozen=True)
class SchemaMeta:
    name: str
    version: str
    title: str
    description: str
    stability: str
    owners: List[str]


@dataclass(frozen=True)
class OutputRecord:
    meta: SchemaMeta
    path: Path
    rel_link: str


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = _yaml.load(handle)  # type: ignore[no-any-return]
    if not isinstance(data, dict):  # pragma: no cover - defensive guard
        raise ValueError(f"Unexpected structure in {path}")
    return data


def _validate_meta(raw: Dict[str, Any], source: Path) -> SchemaMeta:
    try:
        section = raw["schema"]
    except KeyError as exc:  # pragma: no cover - misconfigured input
        raise ValueError(f"Missing 'schema' block in {source}") from exc
    name = section.get("name")
    version = section.get("version")
    if not isinstance(name, str):
        raise ValueError(f"Schema name must be a string in {source}")
    if not isinstance(version, str) or not SEMVER_RE.match(version):
        raise ValueError(
            f"Schema version must be a semver string (got {version!r}) in {source}"
        )
    title = section.get("title") or f"Noēsis {name.title()} Schema"
    description = section.get("description", "")
    stability = section.get("stability", "experimental")
    owners = section.get("owners", [])
    if not isinstance(owners, list):
        raise ValueError(f"Owners must be a list in {source}")
    owners = [str(owner) for owner in owners]
    return SchemaMeta(name=name, version=version, title=title, description=description, stability=str(stability), owners=owners)


def _inject_metadata(node: Any) -> Any:
    if isinstance(node, dict):
        updated: Dict[str, Any] = {}
        for key, value in node.items():
            if key == "stability":
                updated["x-stability"] = value
                continue
            updated[key] = _inject_metadata(value)
        return updated
    if isinstance(node, list):
        return [_inject_metadata(item) for item in node]
    return node


def _build_json_schema(meta: SchemaMeta, payload: Dict[str, Any]) -> Dict[str, Any]:
    annotated = _inject_metadata(payload)
    document: Dict[str, Any] = {
        "$id": f"{SCHEMA_BASE_URL}/{meta.name}/{meta.version}",
        "$schema": JSON_SCHEMA_URL,
        "$schema_name": meta.name,
        "$schema_version": meta.version,
        "title": meta.title,
        "description": meta.description,
        "x-owners": meta.owners,
        "x-stability": meta.stability,
    }
    document.update(annotated)
    return document


def _build_kpi_doc(meta: SchemaMeta, payload: Dict[str, Any]) -> Dict[str, Any]:
    items: Dict[str, Any] = {}
    for key in sorted(payload.keys()):
        definition = payload[key]
        if not isinstance(definition, dict):
            raise ValueError(f"KPI entry {key} must be a mapping")
        normalized = dict(definition)
        normalized.setdefault("stability", meta.stability)
        items[key] = _inject_metadata(normalized)
    return {
        "$id": f"{SCHEMA_BASE_URL}/{meta.name}/{meta.version}",
        "$schema": JSON_SCHEMA_URL,
        "$schema_name": meta.name,
        "$schema_version": meta.version,
        "title": meta.title,
        "description": meta.description,
        "kpis": items,
        "x-owners": meta.owners,
        "x-stability": meta.stability,
    }


def _dump_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _write_if_changed(path: Path, content: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current == content:
            return False
    path.write_text(content, encoding="utf-8")
    return True


def _render_reference_doc(records: List[OutputRecord]) -> str:
    header = """---
title: Schema Index
description: Canonical schema list generated from internal_docs/schema
---

# Schema Index

Schema definitions originate from `internal_docs/schema/*.yaml` and are generated via `python scripts/gen_schema.py`.

| Artifact | Version | Stability | Owners | Download |
| --- | --- | --- | --- | --- |
"""
    rows = []
    for record in sorted(records, key=lambda item: item.meta.name):
        owners = ", ".join(record.meta.owners) if record.meta.owners else "—"
        link = f"/{record.rel_link}"
        rows.append(
            f"| {record.meta.name} | {record.meta.version} | {record.meta.stability} | {owners} | [`{link}`]({link}) |"
        )
    return header + "\n".join(rows) + "\n"


def generate_docs(check_only: bool = False) -> int:
    changed = False
    records: List[OutputRecord] = []
    manifest: Dict[str, str] = {}

    for definition_path in sorted(SCHEMA_SRC_DIR.glob("*.yaml")):
        data = _load_yaml(definition_path)
        meta = _validate_meta(data, definition_path)
        manifest[meta.name] = meta.version

        if "json_schema" in data:
            payload = data["json_schema"]
            if not isinstance(payload, dict):
                raise ValueError(f"json_schema must be a mapping in {definition_path}")
            document = _build_json_schema(meta, payload)
        elif "kpis" in data:
            payload = data["kpis"]
            if not isinstance(payload, dict):
                raise ValueError(f"kpis must be a mapping in {definition_path}")
            document = _build_kpi_doc(meta, payload)
        else:
            raise ValueError(f"{definition_path} must define 'json_schema' or 'kpis'")

        out_dir = SCHEMA_OUT_DIR / meta.name
        out_path = out_dir / f"{meta.version}.json"
        rel_link = f"schema/{meta.name}/{meta.version}.json"
        content = _dump_json(document)
        if _write_if_changed(out_path, content):
            changed = True
        records.append(OutputRecord(meta=meta, path=out_path, rel_link=rel_link))

    manifest_payload = _dump_json({key: manifest[key] for key in sorted(manifest.keys())})
    if _write_if_changed(MANIFEST_PATH, manifest_payload):
        changed = True

    reference_payload = _render_reference_doc(records)
    if _write_if_changed(REFERENCE_DOC, reference_payload):
        changed = True

    if check_only and changed:
        return 2
    return 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate canonical JSON schemas from YAML sources.")
    parser.add_argument("--check", action="store_true", help="Exit with code 2 if output files are stale.")
    args = parser.parse_args(argv)
    try:
        return generate_docs(check_only=args.check)
    except Exception as exc:  # pragma: no cover - surfaces actionable errors
        print(f"schema generation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
