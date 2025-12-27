from __future__ import annotations

from pathlib import Path

FORBIDDEN_PREFIXES = (
    "noesis.infrastructure.",
    "noesis.interfaces.",
    "noesis.usecases.",
    "noesis.domain.",
    "noesis.runtime._",
)


def _iter_source_files() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[2]
    targets = [repo_root / "docs" / "app", repo_root / "examples"]
    files: list[Path] = []
    for base in targets:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".md", ".mdx"}:
                files.append(path)
    return files


def _iter_runtime_files() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[2]
    runtime_root = repo_root / "noesis" / "runtime"
    if not runtime_root.exists():
        return []
    return [path for path in runtime_root.rglob("*.py") if path.is_file()]


def _should_check_line(path: Path, line: str, state: dict) -> bool:
    if path.suffix not in {".md", ".mdx"}:
        return True
    stripped = line.rstrip()
    if stripped.startswith("```"):
        lang = stripped[3:].strip().lower()
        if state.get("in_code"):
            state["in_code"] = False
            state.pop("lang", None)
        else:
            state["in_code"] = True
            state["lang"] = lang or ""
        return False
    if not state.get("in_code"):
        return False
    lang = state.get("lang", "")
    return lang in {"", "python", "py"}


def test_docs_and_examples_do_not_import_private_modules() -> None:
    offenders: list[str] = []
    for path in _iter_source_files():
        state: dict[str, object] = {"in_code": False, "lang": ""}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not _should_check_line(path, line, state):
                continue
            stripped = line.strip()
            if not stripped.startswith(("import", "from")):
                continue
            if any(prefix in stripped for prefix in FORBIDDEN_PREFIXES):
                offenders.append(f"{path}: {stripped}")
    assert not offenders, "Forbidden imports detected:\n" + "\n".join(offenders)


def test_runtime_does_not_import_noesis_learn() -> None:
    offenders: list[str] = []
    for path in _iter_runtime_files():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and "noesis.learn" in stripped:
                offenders.append(f"{path}: {stripped}")
    assert not offenders, "Runtime imports noesis.learn:\n" + "\n".join(offenders)
