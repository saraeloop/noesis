from __future__ import annotations

import json
from pathlib import Path

import pytest

from noesis.runtime.artifacts.writer import ManifestWriter
from noesis.runtime.artifacts.verify import ManifestVerifier
from noesis.runtime.artifacts.signing import HMACManifestSigner, HMACSignatureVerifier
from noesis.runtime.artifacts.manifest import MANIFEST_FILE_NAME
from noesis.trace.events import write_event
from noesis.trace.summary import write_summary
from noesis.runtime.learning import ensure_learn_file, persist_episode_learning
from noesis.runtime.prompt_recorder import PromptRecorder
from noesis.infrastructure.state_repository import EpisodeContext, RuntimeStateRepository
from noesis.domain.artifacts.immutability import ImmutabilityError


def _write_json(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _prepare_run_dir(base: Path, name: str = "ep_test") -> Path:
    run_dir = base / name
    run_dir.mkdir()
    _write_json(run_dir / "summary.json", '{"ok": true}')
    _write_json(run_dir / "state.json", '{"state": "ready"}')
    (run_dir / "events.jsonl").write_text('{"event": "start"}\n', encoding="utf-8")
    return run_dir


def test_manifest_writer_records_known_artifacts(tmp_path: Path) -> None:
    run_dir = _prepare_run_dir(tmp_path)
    (run_dir / "custom.txt").write_text("note", encoding="utf-8")

    writer = ManifestWriter(run_dir=run_dir, episode_id="ep_test")
    manifest = writer.finalize()

    manifest_path = run_dir / MANIFEST_FILE_NAME
    assert manifest_path.exists()
    recorded = {entry.name: entry for entry in manifest.files}
    assert set(recorded) >= {"summary.json", "state.json", "events.jsonl", "custom.txt"}
    assert recorded["summary.json"].sha256.startswith("sha256:")


@pytest.mark.parametrize("filename", ["summary.json", "state.json", "events.jsonl"])
def test_manifest_verifier_detects_tampering(tmp_path: Path, filename: str) -> None:
    run_dir = _prepare_run_dir(tmp_path, f"ep_{filename.replace('.', '_')}")

    writer = ManifestWriter(run_dir=run_dir, episode_id="ep_verify")
    writer.finalize()

    verifier = ManifestVerifier(run_dir=run_dir)
    ok_report = verifier.verify_path(run_dir / MANIFEST_FILE_NAME)
    assert ok_report.status == "ok"

    target = run_dir / filename
    target.write_text("tampered", encoding="utf-8")
    tamper_report = verifier.verify_path(run_dir / MANIFEST_FILE_NAME)
    assert tamper_report.status == "error"
    assert any(issue.name == filename for issue in tamper_report.issues)


def test_manifest_verifier_detects_prompt_tampering(tmp_path: Path) -> None:
    run_dir = _prepare_run_dir(tmp_path, "ep_prompt")
    (run_dir / "prompts.jsonl").write_text('{"prompt": "original"}\n', encoding="utf-8")

    writer = ManifestWriter(run_dir=run_dir, episode_id="ep_prompt")
    writer.finalize()

    verifier = ManifestVerifier(run_dir=run_dir)
    assert verifier.verify_path(run_dir / MANIFEST_FILE_NAME).status == "ok"

    (run_dir / "prompts.jsonl").write_text('{"prompt": "tampered"}\n', encoding="utf-8")
    tamper_report = verifier.verify_path(run_dir / MANIFEST_FILE_NAME)
    assert tamper_report.status == "error"
    assert any(issue.name == "prompts.jsonl" for issue in tamper_report.issues)


def test_manifest_verifier_reports_missing_file(tmp_path: Path) -> None:
    run_dir = _prepare_run_dir(tmp_path, "ep_missing")
    writer = ManifestWriter(run_dir=run_dir, episode_id="ep_missing")
    writer.finalize()

    (run_dir / "events.jsonl").unlink()
    report = ManifestVerifier(run_dir=run_dir).verify_path(run_dir / MANIFEST_FILE_NAME)
    assert report.status == "error"
    assert any(issue.kind == "missing" and issue.name == "events.jsonl" for issue in report.issues)


def test_manifest_verifier_warns_on_untracked_when_not_strict(tmp_path: Path) -> None:
    run_dir = _prepare_run_dir(tmp_path, "ep_warn")
    writer = ManifestWriter(run_dir=run_dir, episode_id="ep_warn")
    writer.finalize()
    (run_dir / "attachments").mkdir()
    (run_dir / "attachments" / "foo.txt").write_text("hi", encoding="utf-8")

    report = ManifestVerifier(run_dir=run_dir, strict=False).verify_path(run_dir / MANIFEST_FILE_NAME)
    assert report.status == "warn"
    assert any(file.name.endswith("attachments/foo.txt") and file.status == "unexpected" for file in report.files)


def test_manifest_verifier_errors_on_untracked_when_strict(tmp_path: Path) -> None:
    run_dir = _prepare_run_dir(tmp_path, "ep_strict")
    writer = ManifestWriter(run_dir=run_dir, episode_id="ep_strict")
    writer.finalize()
    (run_dir / "attachments").mkdir()
    (run_dir / "attachments" / "foo.txt").write_text("hi", encoding="utf-8")

    report = ManifestVerifier(run_dir=run_dir, strict=True).verify_path(run_dir / MANIFEST_FILE_NAME)
    assert report.status == "error"
    assert any(issue.kind == "unexpected_strict" for issue in report.issues)


def test_write_event_after_manifest_fails(tmp_path: Path) -> None:
    run_dir = _prepare_run_dir(tmp_path, "ep_guard")
    ManifestWriter(run_dir=run_dir, episode_id="ep_guard").finalize()

    event = {
        "timestamp": "2024-01-01T00:00:00Z",
        "episode_id": "ep_guard",
        "phase": "test",
        "payload": {},
        "evidence_ids": [],
    }
    with pytest.raises(ImmutabilityError) as exc:
        write_event(run_dir, event, validate=False)
    assert "episode sealed" in str(exc.value)


def test_append_only_allows_events_pre_seal(tmp_path: Path) -> None:
    run_dir = tmp_path / "ep_events"
    run_dir.mkdir()
    event = {
        "timestamp": "2024-01-01T00:00:00Z",
        "episode_id": "ep_events",
        "phase": "test",
        "payload": {},
        "evidence_ids": [],
    }
    write_event(run_dir, dict(event), validate=False)
    write_event(run_dir, dict(event), validate=False)


def test_summary_state_and_learn_writes_block_after_seal(tmp_path: Path) -> None:
    run_dir = tmp_path / "ep_state"
    run_dir.mkdir()

    write_summary(run_dir, {"schema_version": "1.0.0", "episode_id": "ep_state"})

    ctx = EpisodeContext(
        run_dir=run_dir,
        episode_id="ep_state",
        seed=0,
        task="test",
        tags={},
        adapter_label="adapter:test",
        started_at="2024-01-01T00:00:00Z",
    )
    repo = RuntimeStateRepository(context=ctx)
    state = repo.init()

    ensure_learn_file(run_dir)
    persist_episode_learning(
        run_dir,
        episode_id="ep_state",
        agent_id="system",
        payload={"policy_id": "policy:test"},
    )

    ManifestWriter(run_dir=run_dir, episode_id="ep_state").finalize()

    with pytest.raises(ImmutabilityError) as exc:
        write_summary(run_dir, {"schema_version": "1.0.0", "episode_id": "ep_state"})
    assert "episode sealed" in str(exc.value)
    with pytest.raises(ImmutabilityError):
        repo.persist(state)
    with pytest.raises(ImmutabilityError):
        ensure_learn_file(run_dir)
    with pytest.raises(ImmutabilityError):
        persist_episode_learning(
            run_dir,
            episode_id="ep_state",
            agent_id="system",
            payload={"policy_id": "policy:test"},
        )


def test_prompt_recording_blocked_after_seal(tmp_path: Path) -> None:
    run_dir = tmp_path / "ep_prompt_seal"
    run_dir.mkdir()
    recorder = PromptRecorder(
        run_dir=run_dir,
        episode_id="ep_prompt_seal",
        enabled=True,
        mode="hash_only",
    )
    recorder.record(phase="observe", agent_id="tester", rendered="hi")

    ManifestWriter(run_dir=run_dir, episode_id="ep_prompt_seal").finalize()

    with pytest.raises(ImmutabilityError):
        recorder.record(phase="observe", agent_id="tester", rendered="blocked")


def test_manifest_signatures_survive_canonicalization(tmp_path: Path) -> None:
    run_dir = _prepare_run_dir(tmp_path, "ep_signed")
    signer = HMACManifestSigner(key_id="2024-Q4", secret="super-secret")
    writer = ManifestWriter(run_dir=run_dir, episode_id="ep_signed", signer=signer)
    writer.finalize()
    manifest_path = run_dir / MANIFEST_FILE_NAME

    # Rewrite manifest with different spacing to ensure canonical verification works.
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_path.write_text(json.dumps(manifest_data, indent=4), encoding="utf-8")

    verifier = ManifestVerifier(run_dir=run_dir, signature_verifier=HMACSignatureVerifier({"2024-Q4": "super-secret"}))
    report = verifier.verify_path(manifest_path)
    assert report.status == "ok"


def test_hmac_key_rotation_verifier_accepts_old_and_new_keys(tmp_path: Path) -> None:
    run_dir_old = _prepare_run_dir(tmp_path, "ep_old_key")
    run_dir_new = _prepare_run_dir(tmp_path, "ep_new_key")

    old_signer = HMACManifestSigner(key_id="2024-Q3", secret="old")
    new_signer = HMACManifestSigner(key_id="2024-Q4", secret="new")
    ManifestWriter(run_dir=run_dir_old, episode_id="ep_old_key", signer=old_signer).finalize()
    ManifestWriter(run_dir=run_dir_new, episode_id="ep_new_key", signer=new_signer).finalize()

    verifier = ManifestVerifier(
        run_dir=run_dir_old,
        signature_verifier=HMACSignatureVerifier({"2024-Q3": "old", "2024-Q4": "new"}),
    )
    assert verifier.verify_path(run_dir_old / MANIFEST_FILE_NAME).status == "ok"
    verifier_new = ManifestVerifier(
        run_dir=run_dir_new,
        signature_verifier=HMACSignatureVerifier({"2024-Q3": "old", "2024-Q4": "new"}),
    )
    assert verifier_new.verify_path(run_dir_new / MANIFEST_FILE_NAME).status == "ok"
