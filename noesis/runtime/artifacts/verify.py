from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal, Protocol
import time

from .manifest import (
    ArtifactManifest,
    MANIFEST_FILE_NAME,
    ManifestSignature,
    compute_sha256,
    _normalize_name,
)

VerificationKind = Literal["missing", "hash_mismatch", "size_mismatch", "unexpected", "unexpected_strict", "signature", "io"]
FileStatus = Literal["ok", "missing", "hash_mismatch", "size_mismatch", "unexpected"]


@dataclass(frozen=True, slots=True)
class VerificationIssue:
    """Single verification failure entry."""

    name: str
    kind: VerificationKind
    detail: str


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """Aggregated verification summary."""

    manifest_path: Path
    files_checked: int
    issues: tuple[VerificationIssue, ...]
    files: tuple["FileVerification", ...]
    duration_ms: float

    @property
    def status(self) -> Literal["ok", "warn", "error"]:
        if not self.issues:
            return "ok"
        if any(
            issue.kind in {"missing", "hash_mismatch", "size_mismatch", "signature", "io", "unexpected_strict"}
            for issue in self.issues
        ):
            return "error"
        return "warn"

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_path": str(self.manifest_path),
            "files_checked": self.files_checked,
            "issues": [issue.__dict__ for issue in self.issues],
            "files": [file.to_dict() for file in self.files],
            "status": self.status,
            "duration_ms": round(self.duration_ms, 3),
        }


@dataclass(frozen=True, slots=True)
class FileVerification:
    name: str
    expected_sha256: str | None
    actual_sha256: str | None
    expected_size: int | None
    actual_size: int | None
    status: FileStatus

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "expected_sha256": self.expected_sha256,
            "actual_sha256": self.actual_sha256,
            "expected_size": self.expected_size,
            "actual_size": self.actual_size,
            "status": self.status,
        }


class SignatureVerifier(Protocol):
    """Optional verifier for signed manifests."""

    name: str

    def verify(self, payload: bytes, signature: ManifestSignature, *, signer: str | None = None) -> bool: ...


class ManifestVerifier:
    """Validate artifact manifests against the filesystem."""

    def __init__(
        self,
        *,
        run_dir: Path | None = None,
        strict: bool = False,
        signature_verifier: SignatureVerifier | None = None,
    ) -> None:
        self._run_dir = run_dir
        self._strict = strict
        self._signature_verifier = signature_verifier

    def verify_path(self, manifest_path: Path) -> VerificationReport:
        manifest = ArtifactManifest.from_json(manifest_path.read_text(encoding="utf-8"))
        base_dir = self._run_dir or manifest_path.parent
        return self.verify(manifest, base_dir=base_dir, manifest_path=manifest_path)

    def verify(
        self,
        manifest: ArtifactManifest,
        *,
        base_dir: Path | None = None,
        manifest_path: Path | None = None,
    ) -> VerificationReport:
        """
        Verify a manifest object using artifacts rooted at `base_dir`.

        When `strict=True`, report any untracked files under `base_dir`.
        """
        start = time.perf_counter()
        root = base_dir or self._run_dir
        if root is None:
            raise ValueError("ManifestVerifier requires a base_dir or run_dir")
        issues: list[VerificationIssue] = []
        manifest_abspath = manifest_path or root / MANIFEST_FILE_NAME
        files_checked = 0
        present_files = set()
        file_results: list[FileVerification] = []

        for entry in manifest.iter_files():
            target = root / entry.name
            present_files.add(_normalize_name(Path(entry.name)))
            if not target.is_file():
                issues.append(VerificationIssue(name=entry.name, kind="missing", detail="file not found"))
                file_results.append(
                    FileVerification(
                        name=entry.name,
                        expected_sha256=entry.sha256,
                        actual_sha256=None,
                        expected_size=entry.size_bytes,
                        actual_size=None,
                        status="missing",
                    )
                )
                continue
            files_checked += 1
            actual_hash = compute_sha256(target)
            if actual_hash != entry.sha256:
                file_results.append(
                    FileVerification(
                        name=entry.name,
                        expected_sha256=entry.sha256,
                        actual_sha256=actual_hash,
                        expected_size=entry.size_bytes,
                        actual_size=target.stat().st_size,
                        status="hash_mismatch",
                    )
                )
                issues.append(
                    VerificationIssue(
                        name=entry.name,
                        kind="hash_mismatch",
                        detail=f"{actual_hash} != {entry.sha256}",
                    )
                )
                continue
            actual_size = target.stat().st_size
            if actual_size != entry.size_bytes:
                file_results.append(
                    FileVerification(
                        name=entry.name,
                        expected_sha256=entry.sha256,
                        actual_sha256=actual_hash,
                        expected_size=entry.size_bytes,
                        actual_size=actual_size,
                        status="size_mismatch",
                    )
                )
                issues.append(
                    VerificationIssue(
                        name=entry.name,
                        kind="size_mismatch",
                        detail=f"{actual_size} != {entry.size_bytes}",
                    )
                )
            else:
                file_results.append(
                    FileVerification(
                        name=entry.name,
                        expected_sha256=entry.sha256,
                        actual_sha256=actual_hash,
                        expected_size=entry.size_bytes,
                        actual_size=actual_size,
                        status="ok",
                    )
                )

        actual_files = {
            _normalize_name(path.relative_to(root))
            for path in root.rglob("*")
            if path.is_file() and path.name != MANIFEST_FILE_NAME
        }
        extras = sorted(actual_files - present_files)
        for extra in extras:
            kind: VerificationKind = "unexpected_strict" if self._strict else "unexpected"
            issues.append(
                VerificationIssue(
                    name=extra,
                    kind=kind,
                    detail="not tracked by manifest" + (" (strict)" if self._strict else ""),
                )
            )
            file_results.append(
                FileVerification(
                    name=extra,
                    expected_sha256=None,
                    actual_sha256=None,
                    expected_size=None,
                    actual_size=None,
                    status="unexpected",
                )
            )

        if manifest.signature:
            verifier = self._signature_verifier
            if verifier is None:
                issues.append(
                    VerificationIssue(
                        name=str(manifest_abspath),
                        kind="signature",
                        detail="signature present but no verifier configured",
                    )
                )
            else:
                canonical = manifest.without_signature().canonical_json()
                if not verifier.verify(canonical.encode("utf-8"), manifest.signature, signer=manifest.signer):
                    issues.append(
                        VerificationIssue(
                            name=str(manifest_abspath),
                            kind="signature",
                            detail="signature verification failed",
                        )
                    )

        duration_ms = (time.perf_counter() - start) * 1000.0
        return VerificationReport(
            manifest_path=manifest_abspath,
            files_checked=files_checked,
            issues=tuple(issues),
            files=tuple(file_results),
            duration_ms=duration_ms,
        )


__all__ = [
    "ManifestVerifier",
    "VerificationIssue",
    "VerificationReport",
    "FileVerification",
    "SignatureVerifier",
]
