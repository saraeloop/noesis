"""Artifact integrity helpers: manifests, writers, and deterministic IDs."""

__all__ = [
    "ArtifactFile",
    "ArtifactManifest",
    "ArtifactKind",
    "MANIFEST_FILE_NAME",
    "MANIFEST_SCHEMA_VERSION",
    "ManifestWriter",
    "ManifestSigner",
    "ManifestVerifier",
    "VerificationIssue",
    "VerificationReport",
    "FileVerification",
    "EpisodeIds",
    "new_episode_ulid",
    "directive_uuid",
    "governance_uuid",
    "ManifestSignature",
    "HMACManifestSigner",
    "HMACSignatureVerifier",
]


def __getattr__(name: str):  # pragma: no cover - import shim
    if name in {
        "ArtifactFile",
        "ArtifactManifest",
        "ArtifactKind",
        "MANIFEST_FILE_NAME",
        "MANIFEST_SCHEMA_VERSION",
        "ManifestSignature",
    }:
        from . import manifest as _manifest

        return getattr(_manifest, name)
    if name in {"ManifestWriter", "ManifestSigner"}:
        from . import writer as _writer

        return getattr(_writer, name)
    if name in {"ManifestVerifier", "VerificationIssue", "VerificationReport", "FileVerification"}:
        from . import verify as _verify

        return getattr(_verify, name)
    if name in {"EpisodeIds", "new_episode_ulid", "directive_uuid", "governance_uuid"}:
        from . import ids as _ids

        return getattr(_ids, name)
    if name in {"HMACManifestSigner", "HMACSignatureVerifier"}:
        from . import signing as _signing

        return getattr(_signing, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
