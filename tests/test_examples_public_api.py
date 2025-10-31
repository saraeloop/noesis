from __future__ import annotations

import ast
from pathlib import Path


EXAMPLES_ROOT = Path(__file__).resolve().parents[1] / "examples" / "incident_triage"


def _is_type_checking_guard(node: ast.AST) -> bool:
    parent = getattr(node, "parent", None)
    while parent is not None:
        if isinstance(parent, ast.If) and isinstance(parent.test, ast.Name) and parent.test.id == "TYPE_CHECKING":
            return True
        parent = getattr(parent, "parent", None)
    return False


def test_examples_import_public_surface_only():
    for path in EXAMPLES_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                child.parent = parent  # type: ignore[attr-defined]
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if _is_type_checking_guard(node):
                    continue
                assert not node.module.startswith("noesis."), (
                    f"{path} imports private module {node.module}"
                )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "noesis":
                        continue
                    assert not alias.name.startswith("noesis."), (
                        f"{path} imports private module {alias.name}"
                    )
