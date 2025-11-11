from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Iterable, Literal, Mapping, Sequence
import hashlib
import json

from noesis.runtime.utils import now

ArtifactKind = Literal["summary", "state", "events", "learn", "attachment", "custom"]

MANIFEST_FILE_NAME = "manifest.json"
MANIFEST_SCHEMA_VERSION = "manifest/1.0"


def _normalize_name(path: Path | str) -> str:
    if isinstance(path, Path):
        return path.as_posix()
    return str(path).replace("\\", "/")


def compute_sha256(path: Path, *, chunk_size: int = 65536) -> str:
    """Return a `sha256:`-prefixed digest for the given file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


@dataclass(frozen=True, slots=True)
class ArtifactFile:
    """Hash + size metadata for a single artifact file."""

    name: str
    sha256: str
    size_bytes: int
    kind: ArtifactKind = "attachment"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ArtifactFile":
        return cls(
            name=str(payload.get("name", "")),
            sha256=str(payload.get("sha256", "")),
            size_bytes=int(payload.get("size_bytes", 0)),
            kind=str(payload.get("kind", "attachment")) or "attachment",
        )


@dataclass(frozen=True, slots=True)
class ManifestSignature:
    algorithm: str
    key_id: str
    value: str
    signed_at: str
    context: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "alg": self.algorithm,
            "kid": self.key_id,
            "value": self.value,
            "ts": self.signed_at,
        }
        if self.context:
            payload["ctx"] = dict(self.context)
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ManifestSignature":
        context = payload.get("ctx")
        if context is not None and not isinstance(context, Mapping):
            context = None
        return cls(
            algorithm=str(payload.get("alg", "")),
            key_id=str(payload.get("kid", "")),
            value=str(payload.get("value", "")),
            signed_at=str(payload.get("ts", now())),
            context=dict(context) if context else None,
        )


@dataclass(frozen=True, slots=True)
class ArtifactManifest:
    """Structured manifest describing immutable episode artifacts."""

    episode_id: str
    files: Sequence[ArtifactFile]
    schema_version: str = MANIFEST_SCHEMA_VERSION
    created_at: str = field(default_factory=now)
    signer: str | None = None
    signature: ManifestSignature | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "episode_id": self.episode_id,
            "created_at": self.created_at,
            "files": [item.to_dict() for item in self.files],
            "signer": self.signer,
        }
        if self.signature:
            payload["signature"] = self.signature.to_dict()
        return payload

    def to_json(self, *, indent: int | None = 2, sort_keys: bool = True) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            indent=indent,
            sort_keys=sort_keys,
        )

    def canonical_json(self) -> str:
        """Canonical representation suitable for signatures."""
        return self.to_json(indent=None, sort_keys=True)

    def iter_files(self) -> Iterable[ArtifactFile]:
        yield from self.files

    def without_signature(self) -> "ArtifactManifest":
        return replace(self, signature=None, signer=None)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ArtifactManifest":
        files_payload = payload.get("files") or ()
        if not isinstance(files_payload, (list, tuple)):
            files_payload = ()
        files = tuple(ArtifactFile.from_dict(item) for item in files_payload)
        signature_payload = payload.get("signature")
        signature = None
        if isinstance(signature_payload, Mapping):
            signature = ManifestSignature.from_dict(signature_payload)
        return cls(
            schema_version=str(payload.get("schema_version", MANIFEST_SCHEMA_VERSION)),
            episode_id=str(payload.get("episode_id", "")),
            created_at=str(payload.get("created_at", now())),
            files=files,
            signer=payload.get("signer"),
            signature=signature,
        )

    @classmethod
    def from_json(cls, data: str) -> "ArtifactManifest":
        return cls.from_dict(json.loads(data))


__all__ = [
    "ArtifactFile",
    "ArtifactManifest",
    "ArtifactKind",
    "MANIFEST_FILE_NAME",
    "MANIFEST_SCHEMA_VERSION",
    "compute_sha256",
    "ManifestSignature",
]
