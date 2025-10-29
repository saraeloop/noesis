from __future__ import annotations

import importlib
import json
from typing import Any, Callable, Dict, Optional

import sys
import noesis as ns
from noesis import config as _cfg


_BUILTIN_POLICY_ALIASES: Dict[str, str] = {}


def _policy_aliases() -> Dict[str, str]:
    merged = dict(_BUILTIN_POLICY_ALIASES)
    cfg_aliases = _cfg.get().get("policy_aliases") or {}
    merged.update(cfg_aliases)
    return merged


def resolve_policy_spec(spec: Optional[str]) -> Any:
    if spec is None:
        return True
    trimmed = spec.strip()
    lowered = trimmed.lower()
    if lowered in {"on", "true", "yes"}:
        return True
    if lowered in {"off", "false", "no"}:
        return False

    target = _policy_aliases().get(trimmed, trimmed)

    if ":" in target:
        module_name, class_name = target.split(":", 1)
    else:
        parts = target.rsplit(".", 1)
        if len(parts) != 2:
            raise ValueError(
                "Policy must be alias or module:Class / pkg.Class syntax"
            )
        module_name, class_name = parts

    module = importlib.import_module(module_name)
    policy_cls: Callable[..., Any] = getattr(module, class_name)
    return policy_cls()


def parse_tags(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:  # noqa: TRY003
        raise ValueError(f"Invalid JSON for --tags: {raw}") from exc
    if not isinstance(value, dict):
        raise ValueError("--tags JSON must decode to an object")
    return value


def read_task(arg: Optional[str], *, use_stdin: bool) -> str:
    if use_stdin or arg == "-":
        return sys.stdin.read()
    if arg is None:
        raise ValueError("Task prompt required (use --stdin or provide input)")
    return arg


def apply_dir_min(value: Optional[float]) -> None:
    if value is not None:
        ns.set(direction_min_confidence=float(value))
