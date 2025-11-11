from __future__ import annotations

from pathlib import Path
from typing import Any

from noesis.runtime.artifacts import (
    ArtifactManifest,
    ManifestVerifier,
    VerificationReport,
    FileVerification,
    ManifestSignature,
)
from noesis.runtime.artifacts.manifest import MANIFEST_FILE_NAME


def verify_manifest(
    target: str | Path,
    *,
    strict: bool = False,
    signature_verifier: Any | None = None,
) -> VerificationReport:
    """
    Convenience helper for verifying a manifest from user code.

    `target` may be an episode directory, manifest path, or episode id relative to runs_dir.
    """
    manifest_path = _resolve_manifest_path(target)
    run_dir = manifest_path.parent
    verifier = ManifestVerifier(run_dir=run_dir, strict=strict, signature_verifier=signature_verifier)
    return verifier.verify_path(manifest_path)


def load_manifest(target: str | Path) -> ArtifactManifest:
    """Parse and return an `ArtifactManifest` from disk."""
    manifest_path = _resolve_manifest_path(target)
    return ArtifactManifest.from_json(manifest_path.read_text(encoding="utf-8"))


def _resolve_manifest_path(target: str | Path) -> Path:
    path = Path(target).expanduser()
    if path.is_file():
        return path
    if path.is_dir():
        candidate = path / MANIFEST_FILE_NAME
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Cannot find manifest at '{target}'")


__all__ = [
    "verify_manifest",
    "load_manifest",
    "ArtifactManifest",
    "VerificationReport",
    "FileVerification",
    "ManifestSignature",
]
