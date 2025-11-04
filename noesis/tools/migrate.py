from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Dict, Iterable, List, MutableMapping, Sequence, Set

try:
    import libcst as cst
    from libcst.metadata import MetadataWrapper, ParentNodeProvider, QualifiedNameProvider
except ModuleNotFoundError as exc:  # pragma: no cover - import guard
    raise RuntimeError(
        "libcst is required for the migration codemod. Install the optional dependency with "
        "`pip install noesis[migrate]` and retry."
    ) from exc

SUMMARY_SYMBOLS = {
    "load": "read",
    "finalize_summary": "finalize",
}

EVENT_SYMBOLS = {
    "start_event": "start",
    "observe_event": "observe",
    "interpret_event": "interpret",
    "plan_event": "plan",
    "act_event": "act",
    "reflect_event": "reflect",
    "direction_event": "direction",
    "ensure_act_event": "ensure",
    "terminate_event": "terminate",
}

EPISODE_SYMBOLS = {
    "EpisodeStore": "EpisodeIndex",
}

NAME_MAP = {
    **{f"noesis.summary.{old}": ("renamed", new) for old, new in SUMMARY_SYMBOLS.items()},
    **{f"noesis.events.{old}": ("renamed", new) for old, new in EVENT_SYMBOLS.items()},
    "noesis.state.store.EpisodeStore": ("replaced", "EpisodeIndex"),
}

ATTRIBUTE_EPISODE_FULL = "noesis.state.store.EpisodeStore"

TODO_PATTERNS: Mapping[str, re.Pattern[str]] = {
    "noesis.summary.load": re.compile(r"\bnoesis\.summary\.load\b"),
    "noesis.summary.finalize_summary": re.compile(r"\bnoesis\.summary\.finalize_summary\b"),
    "summary.load": re.compile(r"\bsummary\.load\b"),
    "summary.finalize_summary": re.compile(r"\bsummary\.finalize_summary\b"),
    "from noesis.summary import *": re.compile(r"\bfrom\s+noesis\.summary\s+import\s+\*"),
    "from noesis.events import *": re.compile(r"\bfrom\s+noesis\.events\s+import\s+\*"),
    "EpisodeStore": re.compile(r"\bEpisodeStore\b"),
    "noesis.state.store": re.compile(r"\bnoesis\.state\.store\b"),
    "start_event": re.compile(r"\bstart_event\b"),
    "observe_event": re.compile(r"\bobserve_event\b"),
    "interpret_event": re.compile(r"\binterpret_event\b"),
    "plan_event": re.compile(r"\bplan_event\b"),
    "act_event": re.compile(r"\bact_event\b"),
    "reflect_event": re.compile(r"\breflect_event\b"),
    "direction_event": re.compile(r"\bdirection_event\b"),
    "ensure_act_event": re.compile(r"\bensure_act_event\b"),
    "terminate_event": re.compile(r"\bterminate_event\b"),
}


def _module_to_string(module: cst.BaseExpression | None) -> str | None:
    if module is None:
        return None
    parts: List[str] = []
    current = module
    while isinstance(current, cst.Attribute):
        parts.append(current.attr.value)
        current = current.value
    if isinstance(current, cst.Name):
        parts.append(current.value)
    else:
        return None
    return ".".join(reversed(parts))


class ShimMigrationTransformer(cst.CSTTransformer):
    METADATA_DEPENDENCIES = (ParentNodeProvider, QualifiedNameProvider)

    def __init__(self) -> None:
        self.renamed = 0
        self.replaced = 0
        self.changed = False

    def _qualified_names(self, node: cst.CSTNode) -> Set[str]:
        names = self.get_metadata(QualifiedNameProvider, node, default=set())
        return {q.name for q in names}

    def leave_ImportFrom(self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom) -> cst.ImportFrom:
        module_name = _module_to_string(original_node.module)
        names_changed = False
        collected_names: List[cst.ImportAlias] = []
        names_field = updated_node.names
        if isinstance(names_field, Sequence):
            for alias in names_field:
                new_alias = alias
                if isinstance(alias, cst.ImportAlias):
                    target_name = alias.name.value if isinstance(alias.name, cst.Name) else None
                    if module_name == "noesis.summary" and target_name in SUMMARY_SYMBOLS:
                        new_name = SUMMARY_SYMBOLS[target_name]
                        new_alias = alias.with_changes(name=cst.Name(new_name))
                        self.renamed += 1
                        names_changed = True
                    elif module_name == "noesis.events" and target_name in EVENT_SYMBOLS:
                        new_name = EVENT_SYMBOLS[target_name]
                        new_alias = alias.with_changes(name=cst.Name(new_name))
                        self.renamed += 1
                        names_changed = True
                    elif module_name == "noesis.state.store" and target_name in EPISODE_SYMBOLS:
                        new_name = EPISODE_SYMBOLS[target_name]
                        new_alias = alias.with_changes(name=cst.Name(new_name))
                        self.replaced += 1
                        names_changed = True
                collected_names.append(new_alias)

        result = updated_node
        if module_name == "noesis.state.store":
            module_expr = cst.parse_expression("noesis.episode")
            if isinstance(module_expr, cst.BaseExpression):
                result = result.with_changes(module=module_expr)
                self.replaced += 1
                self.changed = True

        if names_changed:
            result = result.with_changes(names=tuple(collected_names))
            self.changed = True
        return result

    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute) -> cst.BaseExpression:
        qualified = self._qualified_names(original_node)
        if ATTRIBUTE_EPISODE_FULL in qualified:
            self.replaced += 1
            self.changed = True
            return cst.parse_expression("noesis.episode.EpisodeIndex")
        for full_name, (kind, new_token) in NAME_MAP.items():
            if full_name in qualified and kind == "renamed":
                self.renamed += 1
                self.changed = True
                return updated_node.with_changes(attr=cst.Name(new_token))
        return updated_node

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.CSTNode:
        qualified = self._qualified_names(original_node)
        for full_name, (kind, new_token) in NAME_MAP.items():
            if full_name in qualified:
                parent = self.get_metadata(ParentNodeProvider, original_node)
                if isinstance(parent, (cst.FunctionDef, cst.ClassDef)) and parent.name is original_node:
                    return updated_node
                _, _, old_token = full_name.rpartition(".")
                if old_token and original_node.value != old_token:
                    continue
                if kind == "renamed":
                    self.renamed += 1
                else:
                    self.replaced += 1
                self.changed = True
                return updated_node.with_changes(value=new_token)
        return updated_node


@dataclass
class MigrationReport:
    renamed: int = 0
    replaced: int = 0
    skipped: int = 0
    todo: MutableMapping[str, Set[str]] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    changed_files: int = 0

    def register_todo(self, path: Path, symbols: Set[str]) -> None:
        if symbols:
            self.todo[str(path)] = symbols

    def todo_items(self) -> List[tuple[str, Set[str]]]:
        return sorted(self.todo.items(), key=lambda item: item[0])

    def to_dict(self) -> Dict[str, object]:
        return {
            "renamed": self.renamed,
            "replaced": self.replaced,
            "skipped": self.skipped,
            "changed_files": self.changed_files,
            "todo": {path: sorted(symbols) for path, symbols in self.todo_items()},
            "errors": self.errors,
        }


def _iter_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(p for p in path.rglob("*.py") if p.is_file())
            yield from sorted(p for p in path.rglob("*.pyi") if p.is_file())
        elif path.suffix in {".py", ".pyi"} and path.exists():
            yield path


def _collect_todo_symbols(source: str) -> Set[str]:
    matches: Set[str] = set()
    for name, pattern in TODO_PATTERNS.items():
        if pattern.search(source):
            matches.add(name)
    return matches


def run_migration(paths: Iterable[Path], *, apply: bool = True) -> MigrationReport:
    report = MigrationReport()
    for file_path in _iter_files(paths):
        try:
            source = file_path.read_text()
        except (OSError, UnicodeDecodeError) as exc:
            report.skipped += 1
            report.errors.append(f"{file_path}: {exc}")
            continue

        try:
            module = cst.parse_module(source)
            wrapper = MetadataWrapper(module, unsafe_skip_copy=True)
            transformer = ShimMigrationTransformer()
            updated = wrapper.visit(transformer)
            new_source = updated.code
        except Exception as exc:  # noqa: BLE001
            report.skipped += 1
            report.errors.append(f"{file_path}: {exc}")
            continue

        report.renamed += transformer.renamed
        report.replaced += transformer.replaced
        if transformer.changed and new_source != source:
            report.changed_files += 1
            if apply:
                file_path.write_text(new_source)
            final_source = new_source
        else:
            final_source = source

        remaining = _collect_todo_symbols(final_source)
        report.register_todo(file_path, remaining)

    return report
