from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Mapping

from noesis.runtime.utils import now

from .manifest import ArtifactManifest, ManifestSignature

_ALGORITHM_MAP = {
    "HS256": hashlib.sha256,
    "HS512": hashlib.sha512,
}


def _normalize_secret(secret: str | bytes) -> bytes:
    if isinstance(secret, bytes):
        return secret
    return secret.encode("utf-8")


class HMACManifestSigner:
    """
    Deterministic signer that produces ManifestSignature payloads using HMAC.

    Example:
        signer = HMACManifestSigner(key_id="build-2024-11", secret=os.environ["NOESIS_MANIFEST_KEY"])
        writer = ManifestWriter(..., signer=signer)
    """

    def __init__(
        self,
        *,
        key_id: str,
        secret: str | bytes,
        algorithm: str = "HS256",
        context: Mapping[str, str] | None = None,
    ) -> None:
        if algorithm not in _ALGORITHM_MAP:
            raise ValueError(f"Unsupported algorithm '{algorithm}'")
        self.key_id = key_id
        self.algorithm = algorithm
        self._secret = _normalize_secret(secret)
        self._context = dict(context or {})

    @property
    def name(self) -> str:
        return self.key_id

    def sign(self, manifest: ArtifactManifest, payload: bytes) -> ManifestSignature:
        digest = hmac.new(self._secret, payload, _ALGORITHM_MAP[self.algorithm]).digest()
        value = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return ManifestSignature(
            algorithm=self.algorithm,
            key_id=self.key_id,
            value=value,
            signed_at=now(),
            context=self._context or None,
        )


class HMACSignatureVerifier:
    """
    Keyring-backed verifier that supports key rotation.

    Provide a mapping of `key_id -> secret`. When manifests rotate to a new key,
    keep the previous entry in the keyring until all artifacts signed with the
    old key age out.
    """

    def __init__(self, keyring: Mapping[str, str | bytes], algorithm: str = "HS256") -> None:
        if algorithm not in _ALGORITHM_MAP:
            raise ValueError(f"Unsupported algorithm '{algorithm}'")
        self._algorithm = algorithm
        self._keyring = {kid: _normalize_secret(secret) for kid, secret in keyring.items()}

    @property
    def name(self) -> str:
        return "hmac"

    def verify(self, payload: bytes, signature: ManifestSignature, *, signer: str | None = None) -> bool:
        secret = self._keyring.get(signature.key_id)
        if secret is None:
            return False
        digest = hmac.new(secret, payload, _ALGORITHM_MAP[self._algorithm]).digest()
        value = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return hmac.compare_digest(value, signature.value)


__all__ = ["HMACManifestSigner", "HMACSignatureVerifier"]
