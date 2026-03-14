from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import json
import sys

import pytest

import noesis as ns
import noesis.core as core
from noesis.domain.tool_contract import (
    AmbiguousPreparedToolInvocationError,
    ApprovalDecisionStatus,
    EffectKind,
    ExecutionContext,
    GovernanceContext,
    PayloadRedactionPolicy,
    PreflightBinding,
    RiskTier,
    SecurityContext,
    ToolApprovalDecision,
    ToolIdentity,
    ToolProtocol,
    UnsupportedToolProtocolError,
)
from noesis.infrastructure.tool_invocation.adapters import SubprocessToolInvocationAdapter
from noesis.infrastructure.tool_invocation.repositories import (
    FileApprovalDecisionRepository,
    FileIdempotencyStore,
    FilePreparedInvocationRepository,
)
from noesis.runtime.state_projection import project_state_projection
from noesis.trace.events import read_events
from noesis.usecases.run_lifecycle import create_run_lifecycle_service
from noesis.usecases.tool_invocation.models import ToolInvocationInput
from noesis.usecases.tool_invocation.runtime_bridge import (
    AllowAllAuthorizer,
    PassthroughAuthenticator,
    ToolRuntimeBridgePorts,
    build_tool_invocation_actuation_bindings,
)


@contextmanager
def _preserve_config():
    original = ns.get()
    try:
        yield
    finally:
        ns.set(**original)


class _IdentityNormalizer:
    def validate_and_normalize(self, *, protocol, tool, payload):
        return dict(payload)


class _StaticPreflight:
    def __init__(self, impact_hash: str) -> None:
        self.impact_hash = impact_hash

    def compute(self, *, invocation):
        return PreflightBinding(impact_hash=self.impact_hash)


def test_approval_required_prepared_write_pauses_before_side_effects(tmp_path: Path) -> None:
    target = tmp_path / "canary-rollout.json"

    with _preserve_config():
        ns.set(runs_dir=str(tmp_path / "runs"), planner_mode="minimal", governance_mode="off")
        episode_id, checkpoint_id, draft_id, run_dir = _create_paused_run(target=target)

        assert episode_id.startswith("ep_")
        assert checkpoint_id.startswith("chk_")
        assert not target.exists()
        assert not (run_dir / "final.json").exists()
        assert not (run_dir / "manifest.json").exists()

        events = read_events(run_dir)
        assert not [event for event in events if event.get("phase") == "act"]
        assert not [event for event in events if event.get("phase") == "terminate"]

        candidate_event = next(event for event in events if event.get("phase") == "action_candidate")
        candidate_tool_event = next(
            event
            for event in events
            if event.get("phase") == "tool" and (event.get("payload") or {}).get("event_name") == "action.candidate_emitted"
        )
        pending_event = next(
            event
            for event in events
            if event.get("phase") == "tool" and (event.get("payload") or {}).get("event_name") == "tool.approval.pending"
        )
        interrupt_event = next(
            event
            for event in events
            if event.get("phase") == "runtime" and event.get("event_type") == "run.interrupt"
        )
        checkpoint_event = next(
            event
            for event in events
            if event.get("phase") == "runtime" and event.get("event_type") == "run.checkpoint"
        )
        projection = project_state_projection(events)

        assert candidate_tool_event["caused_by"] == candidate_event["id"]
        assert candidate_tool_event["id"] in _causal_chain_ids(events, pending_event["id"])
        assert interrupt_event["caused_by"] == pending_event["id"]
        assert checkpoint_event["caused_by"] == interrupt_event["id"]
        assert (pending_event.get("payload") or {}).get("draft_id") == draft_id
        assert projection is not None
        assert projection.status == "interrupted"
        assert projection.links == {"events": "events.jsonl", "learn": "learn.jsonl"}


def test_resume_run_executes_same_prepared_draft_without_reprepare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "apply.out"

    with _preserve_config():
        ns.set(runs_dir=str(tmp_path / "runs"), planner_mode="minimal", governance_mode="off")
        episode_id, checkpoint_id, draft_id, run_dir = _create_paused_run(target=target)
        prepared = FilePreparedInvocationRepository(run_dir=run_dir).load_pending_for_run(run_id=episode_id)
        assert prepared is not None
        _approve(run_dir=run_dir, prepared=prepared)

        before = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        monkeypatch.setattr(
            "noesis.usecases.tool_invocation.runtime_bridge.prepare_tool_invocation",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("resume must not prepare a new draft")),
        )

        resumed_episode_id = ns.resume_run(episode_id, checkpoint_id=checkpoint_id)

        assert resumed_episode_id == episode_id
        assert target.read_text(encoding="utf-8") == "applied\n"
        after = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        assert after.startswith(before)
        assert len(list((run_dir / "tool_invocations" / "prepared").glob("*.json"))) == 1
        assert FilePreparedInvocationRepository(run_dir=run_dir).load_pending_for_run(run_id=episode_id) is None

        events = read_events(run_dir)
        resume_event = next(
            event
            for event in events
            if event.get("phase") == "runtime" and event.get("event_type") == "run.resume"
        )
        candidate_event = next(event for event in events if event.get("phase") == "action_candidate")
        candidate_tool_event = next(
            event
            for event in events
            if event.get("phase") == "tool" and (event.get("payload") or {}).get("event_name") == "action.candidate_emitted"
        )
        pending_event = next(
            event
            for event in events
            if event.get("phase") == "tool" and (event.get("payload") or {}).get("event_name") == "tool.approval.pending"
        )
        interrupt_event = next(
            event
            for event in events
            if event.get("phase") == "runtime" and event.get("event_type") == "run.interrupt"
        )
        checkpoint_event = next(
            event
            for event in events
            if event.get("phase") == "runtime" and event.get("event_type") == "run.checkpoint"
        )
        execution_started = [
            event
            for event in events
            if event.get("phase") == "tool" and (event.get("payload") or {}).get("event_name") == "tool.execution.started"
        ]
        assert len(execution_started) == 1
        assert (execution_started[0].get("payload") or {}).get("draft_id") == draft_id
        assert execution_started[0]["caused_by"] is not None
        chain = _causal_chain_ids(events, execution_started[0]["id"])
        assert candidate_event["id"] in chain
        assert candidate_tool_event["id"] in chain
        assert pending_event["id"] in chain
        assert interrupt_event["id"] in chain
        assert checkpoint_event["id"] in chain
        assert resume_event["id"] in chain
        assert (run_dir / "final.json").exists()
        assert (run_dir / "manifest.json").exists()


def test_resume_run_without_approval_does_not_dispatch_or_finalize(tmp_path: Path) -> None:
    target = tmp_path / "apply.out"

    with _preserve_config():
        ns.set(runs_dir=str(tmp_path / "runs"), planner_mode="minimal", governance_mode="off")
        episode_id, checkpoint_id, _draft_id, run_dir = _create_paused_run(target=target)
        before = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        resumed_episode_id = ns.resume_run(episode_id, checkpoint_id=checkpoint_id)

        assert resumed_episode_id == episode_id
        assert not target.exists()
        assert not (run_dir / "final.json").exists()
        assert not (run_dir / "manifest.json").exists()
        assert _state_outcome_status(run_dir) == "partial"
        after = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        assert after.startswith(before)

        events = read_events(run_dir)
        assert not [
            event
            for event in events
            if event.get("phase") == "tool" and (event.get("payload") or {}).get("event_name") == "tool.execution.started"
        ]
        assert not [event for event in events if event.get("phase") == "act"]
        assert not [event for event in events if event.get("phase") == "terminate"]


def test_resume_run_rejects_ambiguous_pending_drafts_for_run(tmp_path: Path) -> None:
    target = tmp_path / "apply.out"

    with _preserve_config():
        ns.set(runs_dir=str(tmp_path / "runs"), planner_mode="minimal", governance_mode="off")
        episode_id, checkpoint_id, _draft_id, run_dir = _create_paused_run(target=target)
        repository = FilePreparedInvocationRepository(run_dir=run_dir)
        prepared = repository.load_pending_for_run(run_id=episode_id)
        assert prepared is not None
        repository.save(
            replace(
                prepared,
                draft_id=f"{prepared.draft_id}-other",
                request_id="req-canary-other",
            )
        )

        with pytest.raises(AmbiguousPreparedToolInvocationError):
            ns.resume_run(episode_id, checkpoint_id=checkpoint_id)


def test_resume_run_rejects_unsupported_pending_protocol_before_resume_event(tmp_path: Path) -> None:
    target = tmp_path / "apply.out"

    with _preserve_config():
        ns.set(runs_dir=str(tmp_path / "runs"), planner_mode="minimal", governance_mode="off")
        episode_id, checkpoint_id, _draft_id, run_dir = _create_paused_run(target=target)
        repository = FilePreparedInvocationRepository(run_dir=run_dir)
        prepared = repository.load_pending_for_run(run_id=episode_id)
        assert prepared is not None
        repository.save(replace(prepared, protocol=ToolProtocol.HTTP))
        before = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        before_events = read_events(run_dir)

        with pytest.raises(UnsupportedToolProtocolError):
            ns.resume_run(episode_id, checkpoint_id=checkpoint_id)

        after = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        assert after == before
        after_events = read_events(run_dir)
        assert len(after_events) == len(before_events)
        assert not [
            event
            for event in after_events
            if event.get("phase") == "runtime" and event.get("event_type") == "run.resume"
        ]


def test_resume_run_rejects_approval_impact_hash_mismatch_without_dispatch(tmp_path: Path) -> None:
    target = tmp_path / "apply.out"

    with _preserve_config():
        ns.set(runs_dir=str(tmp_path / "runs"), planner_mode="minimal", governance_mode="off")
        episode_id, checkpoint_id, _draft_id, run_dir = _create_paused_run(
            target=target,
            preflight=_StaticPreflight("sha256:impact-expected"),
        )
        prepared = FilePreparedInvocationRepository(run_dir=run_dir).load_pending_for_run(run_id=episode_id)
        assert prepared is not None
        _approve(run_dir=run_dir, prepared=prepared, impact_hash="sha256:impact-wrong")
        before = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        resumed_episode_id = ns.resume_run(episode_id, checkpoint_id=checkpoint_id)

        assert resumed_episode_id == episode_id
        assert not target.exists()
        assert not (run_dir / "final.json").exists()
        after = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        assert after.startswith(before)
        assert FilePreparedInvocationRepository(run_dir=run_dir).load_pending_for_run(run_id=episode_id) is not None


def test_resume_run_rejects_approval_fingerprint_mismatch_without_dispatch(tmp_path: Path) -> None:
    target = tmp_path / "apply.out"

    with _preserve_config():
        ns.set(runs_dir=str(tmp_path / "runs"), planner_mode="minimal", governance_mode="off")
        episode_id, checkpoint_id, _draft_id, run_dir = _create_paused_run(target=target)
        prepared = FilePreparedInvocationRepository(run_dir=run_dir).load_pending_for_run(run_id=episode_id)
        assert prepared is not None
        _approve(run_dir=run_dir, prepared=prepared, reviewed_fingerprint="sha256:fingerprint-wrong")
        before = (run_dir / "events.jsonl").read_text(encoding="utf-8")

        resumed_episode_id = ns.resume_run(episode_id, checkpoint_id=checkpoint_id)

        assert resumed_episode_id == episode_id
        assert not target.exists()
        assert not (run_dir / "final.json").exists()
        after = (run_dir / "events.jsonl").read_text(encoding="utf-8")
        assert after.startswith(before)
        assert FilePreparedInvocationRepository(run_dir=run_dir).load_pending_for_run(run_id=episode_id) is not None


def test_prepare_bridge_rejects_non_subprocess_protocol_without_persisting_draft(tmp_path: Path) -> None:
    target = tmp_path / "apply.out"

    with _preserve_config():
        ns.set(runs_dir=str(tmp_path / "runs"), planner_mode="minimal", governance_mode="off")
        setup = core._bootstrap_episode(
            task="apply canary rollout",
            seed=0,
            tags=None,
            raw_using_label="core.minimal",
            adapter_label="adapter:core.minimal",
            context=core.get_context(),
            workspace=None,
            verify=(),
            intuition=False,
            determinism=None,
        )
        run_dir = setup.ctx.run_dir
        ports = ToolRuntimeBridgePorts(
            prepared_repository=FilePreparedInvocationRepository(run_dir=run_dir),
            approval_repository=FileApprovalDecisionRepository(run_dir=run_dir),
            idempotency_store=FileIdempotencyStore(run_dir=run_dir),
            dispatch=SubprocessToolInvocationAdapter(),
            normalizer=_IdentityNormalizer(),
            authenticator=PassthroughAuthenticator(),
            authorizer=AllowAllAuthorizer(),
        )
        lifecycle = create_run_lifecycle_service(context=core.get_context(), workspace=None)
        bindings = build_tool_invocation_actuation_bindings(
            request_factory=lambda run_id: _tool_request(
                run_id=run_id,
                target=target,
                draft_id=f"draft:{run_id}:req-http",
                protocol=ToolProtocol.HTTP,
            ),
            run_dir=run_dir,
            ports=ports,
            run_lifecycle=lifecycle,
            now_fn=setup.now_fn,
            id_factory=setup.event_id_factory or core.uuid4,
        )

        episode_id = core._run_episode(
            setup=setup,
            task="apply canary rollout",
            seed=0,
            tags=None,
            using=None,
            actuation_bindings=bindings,
        )

        assert episode_id == setup.ctx.episode_id
        assert not target.exists()
        prepared_root = run_dir / "tool_invocations" / "prepared"
        assert not prepared_root.exists() or list(prepared_root.glob("*.json")) == []
        checkpoints_root = run_dir / "checkpoints"
        assert not checkpoints_root.exists() or list(checkpoints_root.glob("*/checkpoint.json")) == []


def _create_paused_run(
    *,
    target: Path,
    preflight: _StaticPreflight | None = None,
) -> tuple[str, str, str, Path]:
    setup = core._bootstrap_episode(
        task="apply canary rollout",
        seed=0,
        tags=None,
        raw_using_label="core.minimal",
        adapter_label="adapter:core.minimal",
        context=core.get_context(),
        workspace=None,
        verify=(),
        intuition=False,
        determinism=None,
    )
    run_dir = setup.ctx.run_dir
    ports = ToolRuntimeBridgePorts(
        prepared_repository=FilePreparedInvocationRepository(run_dir=run_dir),
        approval_repository=FileApprovalDecisionRepository(run_dir=run_dir),
        idempotency_store=FileIdempotencyStore(run_dir=run_dir),
        dispatch=SubprocessToolInvocationAdapter(),
        normalizer=_IdentityNormalizer(),
        authenticator=PassthroughAuthenticator(),
        authorizer=AllowAllAuthorizer(),
        preflight=preflight,
    )
    lifecycle = create_run_lifecycle_service(context=core.get_context(), workspace=None)
    draft_id = f"draft:{setup.ctx.episode_id}:req-canary"
    bindings = build_tool_invocation_actuation_bindings(
        request_factory=lambda run_id: _tool_request(run_id=run_id, target=target, draft_id=draft_id),
        run_dir=run_dir,
        ports=ports,
        run_lifecycle=lifecycle,
        now_fn=setup.now_fn,
        id_factory=setup.event_id_factory or core.uuid4,
    )

    episode_id = core._run_episode(
        setup=setup,
        task="apply canary rollout",
        seed=0,
        tags=None,
        using=None,
        actuation_bindings=bindings,
    )

    checkpoint_files = list((run_dir / "checkpoints").glob("*/checkpoint.json"))
    assert len(checkpoint_files) == 1
    checkpoint_id = checkpoint_files[0].parent.name
    return episode_id, checkpoint_id, draft_id, run_dir


def _tool_request(
    *,
    run_id: str,
    target: Path,
    draft_id: str,
    protocol: ToolProtocol = ToolProtocol.SUBPROCESS,
) -> ToolInvocationInput:
    return ToolInvocationInput(
        run_id=run_id,
        request_id="req-canary",
        protocol=protocol,
        tool=ToolIdentity(namespace="deploy", name="apply_config", version="1"),
        raw_payload={
            "argv": [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; "
                    f"Path({str(target)!r}).write_text('applied\\n', encoding='utf-8')"
                ),
            ],
            "cwd": str(target.parent),
            "env": None,
            "timeout_ms": 1_000,
        },
        execution=ExecutionContext(timeout_ms=1_000, retry_limit=0, idempotency_key="idem-canary"),
        security=SecurityContext(
            principal_id="user:milo",
            scopes=("deploy:write",),
            policy_scope="prod/canary",
            authn_method="test",
            credential_ref="secret:deploy-token",
        ),
        governance=GovernanceContext(
            effect_kind=EffectKind.WRITE,
            risk_tier=RiskTier.HIGH,
            candidate_id=None,
            requires_approval=True,
            tags=("deploy", "canary"),
        ),
        redaction_policy=PayloadRedactionPolicy(redact_fields=("token",)),
        draft_id=draft_id,
    )


def _approve(
    *,
    run_dir: Path,
    prepared,
    impact_hash: str | None = None,
    reviewed_fingerprint: str | None = None,
) -> None:
    FileApprovalDecisionRepository(run_dir=run_dir).save(
        ToolApprovalDecision(
            decision_id="decision-1",
            run_id=prepared.run_id,
            request_id=prepared.request_id,
            candidate_id=prepared.governance.candidate_id,
            draft_id=prepared.draft_id,
            status=ApprovalDecisionStatus.APPROVED,
            reviewed_fingerprint=reviewed_fingerprint or prepared.payload.request_fingerprint,
            impact_hash=(impact_hash if impact_hash is not None else prepared.preflight.impact_hash if prepared.preflight else None),
            approver_id="approver:milo",
            approval_token_ref="approval:1",
        )
    )


def _causal_chain_ids(events: list[dict[str, object]], leaf_id: str) -> set[str]:
    by_id = {str(event.get("id")): event for event in events if isinstance(event.get("id"), str)}
    chain: set[str] = set()
    current = leaf_id
    while current in by_id and current not in chain:
        chain.add(current)
        caused_by = by_id[current].get("caused_by")
        if not isinstance(caused_by, str):
            break
        current = caused_by
    return chain


def _state_outcome_status(run_dir: Path) -> str:
    payload = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    outcomes = payload.get("outcomes")
    if not isinstance(outcomes, dict):
        raise AssertionError("state.json missing outcomes block")
    status = outcomes.get("status")
    if not isinstance(status, str):
        raise AssertionError("state.json missing outcomes.status")
    return status
