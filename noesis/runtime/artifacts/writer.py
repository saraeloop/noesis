from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Dict, Iterator, Protocol

from noesis.runtime.serialization import atomic_write_text

from .manifest import (
    ArtifactFile,
    ArtifactManifest,
    ArtifactKind,
    MANIFEST_FILE_NAME,
    MANIFEST_SCHEMA_VERSION,
    ManifestSignature,
    compute_sha256,
    _normalize_name,
)

DEFAULT_ARTIFACTS: tuple[tuple[str, ArtifactKind], ...] = (
    ("summary.json", "summary"),
    ("state.json", "state"),
    ("events.jsonl", "events"),
    ("learn.jsonl", "learn"),
)

# TODO(saraeloop): stream events.jsonl hashing during writes to avoid double I/O on large traces.


class ManifestSigner(Protocol):
    """Interface for optional manifest signing implementations."""

    name: str

    def sign(self, manifest: ArtifactManifest, payload: bytes) -> ManifestSignature: ...


class ManifestWriter:
    """Collects artifact hashes and emits `manifest.json` for an episode run."""

    def __init__(
        self,
        *,
        run_dir: Path,
        episode_id: str,
        schema_version: str = MANIFEST_SCHEMA_VERSION,
        signer: ManifestSigner | None = None,
    ) -> None:
        self._run_dir = run_dir
        self._episode_id = episode_id
        self._schema_version = schema_version
        self._signer = signer
        self._tracked: Dict[str, ArtifactFile] = {}

    @property
    def manifest_path(self) -> Path:
        return self._run_dir / MANIFEST_FILE_NAME

    def track_file(self, path: Path | str, *, kind: ArtifactKind = "attachment") -> ArtifactFile:
        """
        Register a file to include in the manifest.

        `path` may be absolute or relative to `run_dir`. The file must exist.
        """
        resolved = self._run_dir / path if not isinstance(path, Path) else path
        if not resolved.is_file():
            raise FileNotFoundError(resolved)
        try:
            relative = resolved.relative_to(self._run_dir)
        except ValueError as err:
            raise ValueError(f"{resolved} is outside run_dir {self._run_dir}") from err
        artifact = self._build_artifact(relative, kind=kind)
        self._tracked[artifact.name] = artifact
        return artifact

    def finalize(self, *, include_untracked: bool = True) -> ArtifactManifest:
        """Write manifest.json and return the manifest object."""
        self._add_default_artifacts()
        if include_untracked:
            self._include_untracked()
        files = tuple(sorted(self._tracked.values(), key=lambda item: item.name))
        manifest = ArtifactManifest(
            episode_id=self._episode_id,
            schema_version=self._schema_version,
            files=files,
        )
        payload = manifest.canonical_json()
        signer = self._signer
        if signer is not None:
            unsigned = manifest.without_signature()
            canonical = unsigned.canonical_json()
            signature = signer.sign(unsigned, canonical.encode("utf-8"))
            manifest = replace(manifest, signer=getattr(signer, "name", signature.key_id), signature=signature)
            payload = manifest.canonical_json()
        atomic_write_text(self.manifest_path, payload)
        return manifest

    def _build_artifact(self, relative: Path, *, kind: ArtifactKind) -> ArtifactFile:
        path = self._run_dir / relative
        stat = path.stat()
        return ArtifactFile(
            name=_normalize_name(relative),
            sha256=compute_sha256(path),
            size_bytes=stat.st_size,
            kind=kind,
        )

    def _add_default_artifacts(self) -> None:
        for name, kind in DEFAULT_ARTIFACTS:
            path = self._run_dir / name
            if not path.is_file():
                continue
            normalized = _normalize_name(Path(name))
            if normalized in self._tracked:
                continue
            self._tracked[normalized] = self._build_artifact(Path(name), kind=kind)

    def _include_untracked(self) -> None:
        for path in self._iter_run_files():
            if path.name == MANIFEST_FILE_NAME:
                continue
            normalized = _normalize_name(path)
            if normalized in self._tracked:
                continue
            self._tracked[normalized] = self._build_artifact(path, kind="attachment")

    def _iter_run_files(self) -> Iterator[Path]:
        for path in self._run_dir.rglob("*"):
            if path.is_file():
                try:
                    relative = path.relative_to(self._run_dir)
                except ValueError:
                    continue
                yield relative


__all__ = ["ManifestWriter", "ManifestSigner", "DEFAULT_ARTIFACTS"]
