# ADR-002 — Artifact Immutability & Manifest

- **Status:** Accepted
- **Date:** 2024-11-11
- **Owner:** Sara Loera (saraeloop)
- **Reviewers:** Core Engineering, QA
- **Related roadmap items:** Phase 0 “Road to v1.0.0”, ADR-001, ADR-003

---

## 1. Context

Phase 0 requires “write-once artifacts with hashes” before feature work. Today each episode creates `summary.json`, `state.json`, `events.jsonl`, and occasionally `learn.jsonl`, but there is no ledger proving what was written, whether the files changed post-run, or how IDs relate to lineage. IDs are timestamp-based, per-file writes are not atomic, and there is no CLI to verify tampering. This blocks the trust spine: without content-addressable artifacts, we cannot promise deterministic replays, compliance cannot audit runs, and remote stores cannot deduplicate or attest to integrity.

## 2. Decision

Introduce a content-addressed artifact model: every episode writes its payloads via temp files + atomic renames, emits a `manifest.json` capturing file hashes, sizes, created_at, and optional HMAC signatures, and uses ULID/UUIDv5 ID policies for episodes/directives/governance. A companion CLI command verifies manifests (hashes & signatures) locally or on remote stores.

### 2.1 Module structure

```
noesis/runtime/artifacts/
├── __init__.py           # Public exports: ArtifactManifest, ManifestWriter, ManifestVerifier
├── manifest.py           # Dataclasses + schema for manifest.json (files[], sha256, created_at, signer info)
├── writer.py             # Atomic file writer + manifest builder; wraps summary/state/event writes
├── ids.py                # ULID episode ID generator + UUIDv5 derivation helpers
├── verify.py             # Manifest verification utilities (hash check, HMAC, reporting)
└── cli.py                # Hook for `noesis artifacts verify <episode>` command
```

- **Entities:** `ArtifactFile`, `ArtifactManifest`, `EpisodeIds`—pure dataclasses describing immutable state.
- **Use cases:** `ManifestWriter` orchestrates atomic writes and manifest generation; `ManifestVerifier` consumes manifests and returns a diagnostics report.
- **Interface adapters:** CLI command + diagnostics integrate with existing `noesis` CLI registry; `EpisodeRunner` uses the writer to persist artifacts.
- **Infrastructure:** Underlying filesystem interactions (temp files, HMAC key provider) remain in writer/verify modules.

### 2.2 Core code sketch

```python
# noesis/runtime/artifacts/manifest.py
@dataclass(slots=True, frozen=True)
class ArtifactFile:
    name: str
    sha256: str
    size_bytes: int
    kind: Literal["summary", "state", "events", "learn", "custom"]

@dataclass(slots=True, frozen=True)
class ArtifactManifest:
    schema_version: str
    episode_id: str
    created_at: str
    files: tuple[ArtifactFile, ...]
    signer: Optional[str] = None
    signature: Optional[str] = None

    def to_dict(self) -> dict[str, Any]: ...

# noesis/runtime/artifacts/writer.py
class ManifestWriter:
    def __init__(self, *, run_dir: Path, signer: ManifestSigner | None = None) -> None: ...

    def write_json(self, name: str, payload: dict[str, Any]) -> Path:
        """Write JSON atomically via temp file + rename; return final path."""

    def finalize(self) -> ArtifactManifest:
        """Hash all known files, produce manifest.json, and optionally sign it."""

# noesis/runtime/artifacts/ids.py
def new_episode_ulid(seed: int) -> str: ...
def directive_uuid(episode_id: str, step_index: int, rule: str) -> str: ...

# noesis/runtime/artifacts/verify.py
class ManifestVerifier:
    def verify(self, manifest: ArtifactManifest) -> VerificationReport: ...
```

### 2.3 Test plan

```python
def test_manifest_writer_atomic(tmp_path):
    writer = ManifestWriter(run_dir=tmp_path)
    writer.write_json("summary.json", {"ok": True})
    writer.write_json("state.json", {"plan": []})
    manifest = writer.finalize()
    assert (tmp_path / "manifest.json").exists()
    assert all(Path(tmp_path / f.name).exists() for f in manifest.files)
    assert all(f.sha256.startswith("sha256:") for f in manifest.files)

def test_manifest_verifier_detects_tamper(tmp_path):
    ...
    Path(tmp_path / "summary.json").write_text("tampered")
    report = ManifestVerifier().verify(manifest)
    assert report.status == "error"
```

### 2.4 Integration points

1. `noesis/state/episode.py` (`begin_episode`) switches to ULID IDs via `ids.new_episode_ulid`.
2. `noesis/core._run_impl` replaces manual `write_summary`/`write_event` calls with `ManifestWriter`, ensuring atomic writes + manifest emission.
3. `EpisodeIndex` stores the manifest path/sha for quick lookup.
4. CLI adds `noesis artifacts verify <episode_dir>` (JSON + pretty output) and diagnostics include manifest verification in `--check-all`.
5. `tests/golden` fixtures updated with `manifest.json`.

### 2.5 Clean Architecture mapping

- **Entities:** `ArtifactManifest`, `EpisodeIds`.
- **Use cases:** `ManifestWriter`, `ManifestVerifier`.
- **Interface adapters:** CLI command, diagnostics hook.
- **Infrastructure:** Filesystem writer, HMAC signer, ID generators.

## 3. Consequences

- Every episode directory now contains a manifest capturing hashes, sizes, creation times, and optional signatures—tampering is detectable.
- IDs become globally unique and time-sortable (ULID for episodes, UUIDv5 for directives/governance/events), enabling deterministic lineage.
- Atomic writes eliminate partially written JSON when processes crash.
- Operators gain a CLI to verify artifacts locally or in CI before shipping bundles.
- Replay harnesses can quickly validate traces by comparing manifest hashes.

## 4. Alternatives considered

1. **Keep ad-hoc per-file writes + timestamp IDs.** Rejected: cannot guarantee immutability or collision resistance.
2. **Use git-like content-addressable storage per file.** Deferred: storing blobs by hash complicates CLI ergonomics; manifest is simpler while still tamper-evident.
3. **Rely on OS-level immutability (chattr/ACLs).** Rejected: platform-specific, inaccessible in most environments, does not help with remote stores.

## 5. Acceptance criteria

- `manifest.json` exists for every episode with sha256 + size for `summary.json`, `state.json`, `events.jsonl`, `learn.jsonl` (when present), and any attachments.
- Episode IDs are ULIDs; directive/governance IDs derived via UUIDv5 as documented.
- Writes are atomic (tests simulate crash by killing process mid-write).
- `noesis artifacts verify` returns non-zero when hashes mismatch or files missing.
- Diagnostics run manifest verification within `noesis diagnostics --check-all`.
- Release checklist updated to include manifest verification step.

## 6. Migration plan

1. Implement ID helpers + manifest writer in parallel with current code behind feature flag (dual-write existing JSON + manifest).
2. Add CLI verification command + documentation.
3. Flip default to manifest mode; keep backward-compatible reads for legacy episodes (manifest optional).
4. Update golden fixtures/tests to require manifest presence.
5. Remove legacy ID generator once consumers migrate.

## 7. Open questions / risks

- HMAC key management: where is the signing key stored, and how do teams rotate it? (Proposal: allow configurable key provider via session ports; document rotation steps).
- Remote artifact stores (S3/NFS): need guidance on how manifest verification works when files are not on local disk.
- Manifest schema versioning: do we embed schema refs per file entry? (Likely yes—`"schema_version": "manifest/1.0"`).
- Performance: hashing large `events.jsonl` may add latency; consider streaming hash during write to avoid double I/O.

## 8. References

- ROADMAP Phase 0 blocking items (artifact integrity & IDs).
- `noesis/trace/summary.py`, `noesis/trace/events.py` (current write helpers).
- `noesis/episode.py`, `noesis/state/episode.py` (episode initialization).
- Existing CLI patterns (`noesis/cli/commands/*`) for adding `artifacts verify`.
