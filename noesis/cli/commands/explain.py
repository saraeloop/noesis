"""Explain command: turns 'veto → now what?' into actionable explanation."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Any

from ..context import CLIContext
from ..render.base import OutputRenderer
from ..query import load_episode_dir, read_summary, iter_events


# ─────────────────────────────────────────────────────────────────────────────
# VIEW MODEL
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GovernanceDecision:
    """Governance decision details."""

    decision: str  # veto | audit | allow
    enforced: bool
    mode: str  # enforce | audit | off
    rule_id: str | None
    policy_id: str | None
    policy_version: str | None
    score: float | None
    message: str | None


@dataclass(frozen=True)
class IntuitionAdvice:
    """Intuition advice from the episode."""

    advice: str
    confidence: float | None


@dataclass(frozen=True)
class DirectionBlock:
    """Direction event that was blocked."""

    status: str
    reason: str
    rule_id: str | None


@dataclass(frozen=True)
class CausalStep:
    """A step in the causal chain."""

    phase: str
    status: str | None


@dataclass(frozen=True)
class ExplainVM:
    """View model for explain command output."""

    episode_id: str
    task: str
    status: str  # vetoed | audit | ok
    governance: GovernanceDecision | None
    intuition_advice: list[IntuitionAdvice]
    direction_blocks: list[DirectionBlock]
    risky_tokens: list[str]
    causal_chain: list[CausalStep]
    next_actions: list[str]


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACTION LOGIC
# ─────────────────────────────────────────────────────────────────────────────

# Tokens that indicate potentially risky operations
RISKY_PATTERNS = [
    "/prod", "prod-", "production",
    "delete", "destroy", "remove", "drop", "truncate",
    "wipe", "erase", "purge",
    "force", "--force", "-f",
    "sudo", "root", "admin",
    "password", "secret", "credential", "token", "key",
    "database", "db", "sql",
]


def _extract_risky_tokens(task: str) -> list[str]:
    """Extract potentially risky tokens from task string."""
    task_lower = task.lower()
    found = []
    for pattern in RISKY_PATTERNS:
        if pattern in task_lower:
            found.append(pattern)
    return found[:5]  # Limit to top 5


def _build_explain_vm(
    episode_id: str,
    summary: dict[str, Any] | None,
    events: list[dict[str, Any]],
) -> ExplainVM:
    """Build ExplainVM from artifacts."""
    summary = summary or {}
    task = summary.get("task", "(no task)")
    status = summary.get("status", "unknown")

    governance: GovernanceDecision | None = None
    intuition_advice: list[IntuitionAdvice] = []
    direction_blocks: list[DirectionBlock] = []
    causal_chain: list[CausalStep] = []

    for event in events:
        phase = event.get("phase", "")
        payload = event.get("payload", {}) or {}

        if phase == "governance":
            decision = payload.get("decision", "")
            if decision in ("veto", "audit", "allow"):
                governance = GovernanceDecision(
                    decision=decision,
                    enforced=bool(payload.get("enforced")),
                    mode=payload.get("mode", "unknown"),
                    rule_id=payload.get("rule_id"),
                    policy_id=payload.get("policy_id"),
                    policy_version=payload.get("policy_version"),
                    score=payload.get("score"),
                    message=payload.get("message"),
                )
                causal_chain.append(CausalStep(phase="governance", status=decision))

        elif phase == "intuition":
            advice = payload.get("advice")
            if advice:
                intuition_advice.append(
                    IntuitionAdvice(
                        advice=str(advice),
                        confidence=payload.get("confidence"),
                    )
                )

        elif phase == "direction":
            dir_status = payload.get("status", "")
            if dir_status == "blocked":
                direction_blocks.append(
                    DirectionBlock(
                        status=dir_status,
                        reason=payload.get("reason", "unknown"),
                        rule_id=payload.get("rule_id"),
                    )
                )
                causal_chain.append(CausalStep(phase="direction", status="blocked"))

        elif phase == "plan":
            causal_chain.append(CausalStep(phase="plan", status=None))

        elif phase == "terminate":
            term_status = payload.get("status", "")
            causal_chain.append(CausalStep(phase="terminate", status=term_status))

    # Extract risky tokens from task
    risky_tokens = _extract_risky_tokens(task)

    # Build next actions
    next_actions = []
    if status == "vetoed":
        next_actions = [
            f"noesis view {episode_id}",
            f"noesis rerun {episode_id} --audit",
        ]
    else:
        next_actions = [
            f"noesis view {episode_id}",
            f"noesis events {episode_id}",
        ]

    return ExplainVM(
        episode_id=episode_id,
        task=task,
        status=status,
        governance=governance,
        intuition_advice=intuition_advice,
        direction_blocks=direction_blocks,
        risky_tokens=risky_tokens,
        causal_chain=causal_chain,
        next_actions=next_actions,
    )


# ─────────────────────────────────────────────────────────────────────────────
# COMMAND
# ─────────────────────────────────────────────────────────────────────────────


class ExplainCommand:
    name = "explain"
    help = "Explain why an episode was vetoed or audited"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("episode_id", help="Episode identifier")
        parser.add_argument("-j", "--json", action="store_true", help="JSON output")
        parser.add_argument("-q", "--quiet", action="store_true", help="Suppress extra output")

    def run(self, args: argparse.Namespace, ctx: CLIContext, renderer: OutputRenderer) -> int:
        episode_id = args.episode_id
        ep_dir = load_episode_dir(episode_id, ctx.config_snapshot.runs_dir)

        if not ep_dir.exists():
            # Try remote
            try:
                summary = ctx.ns.summary.read(episode_id, context=ctx.runtime_context)
                events = list(ctx.ns.events.read(episode_id, context=ctx.runtime_context))
            except Exception as exc:  # noqa: BLE001
                renderer.echo(f"Episode not found: {episode_id}")
                return 1
        else:
            summary = read_summary(ep_dir)
            events = list(iter_events(ep_dir))

        vm = _build_explain_vm(episode_id, summary, events)

        if args.json:
            renderer.json(_vm_to_dict(vm))
        else:
            _render_explain(renderer, vm)

        return 0


def _vm_to_dict(vm: ExplainVM) -> dict[str, Any]:
    """Convert ExplainVM to JSON-serializable dict."""
    return {
        "episode_id": vm.episode_id,
        "task": vm.task,
        "status": vm.status,
        "governance": {
            "decision": vm.governance.decision,
            "enforced": vm.governance.enforced,
            "mode": vm.governance.mode,
            "rule_id": vm.governance.rule_id,
            "policy_id": vm.governance.policy_id,
            "policy_version": vm.governance.policy_version,
            "score": vm.governance.score,
            "message": vm.governance.message,
        } if vm.governance else None,
        "intuition_advice": [
            {"advice": a.advice, "confidence": a.confidence}
            for a in vm.intuition_advice
        ],
        "direction_blocks": [
            {"status": d.status, "reason": d.reason, "rule_id": d.rule_id}
            for d in vm.direction_blocks
        ],
        "risky_tokens": vm.risky_tokens,
        "causal_chain": [
            {"phase": s.phase, "status": s.status}
            for s in vm.causal_chain
        ],
        "next_actions": vm.next_actions,
    }


def _render_explain(renderer: OutputRenderer, vm: ExplainVM) -> None:
    """Render explain output using the renderer."""
    # Use the dedicated print_explain method if available
    if hasattr(renderer, "print_explain"):
        renderer.print_explain(vm)
    else:
        # Fallback to basic output
        _render_explain_plain(renderer, vm)


def _render_explain_plain(renderer: OutputRenderer, vm: ExplainVM) -> None:
    """Fallback plain text rendering."""
    renderer.echo(f"Episode: {vm.episode_id}")
    renderer.echo(f"Task: {vm.task}")
    renderer.echo(f"Status: {vm.status.upper()}")

    if vm.governance:
        gov = vm.governance
        renderer.echo("")
        renderer.echo("Governance Decision")
        renderer.echo(f"  decision: {gov.decision.upper()}")
        renderer.echo(f"  enforced: {gov.enforced}")
        renderer.echo(f"  mode: {gov.mode}")
        if gov.rule_id:
            renderer.echo(f"  rule_id: {gov.rule_id}")
        if gov.policy_id:
            renderer.echo(f"  policy_id: {gov.policy_id}")
        if gov.score is not None:
            renderer.echo(f"  score: {gov.score:.2f}")
        if gov.message:
            renderer.echo(f"  message: {gov.message}")

    if vm.intuition_advice:
        renderer.echo("")
        renderer.echo("Intuition Advice")
        for advice in vm.intuition_advice:
            conf = f" (confidence={advice.confidence:.2f})" if advice.confidence is not None else ""
            renderer.echo(f"  - {advice.advice}{conf}")

    if vm.direction_blocks:
        renderer.echo("")
        renderer.echo("Direction Blocks")
        for block in vm.direction_blocks:
            renderer.echo(f"  - {block.status}: {block.reason}")
            if block.rule_id:
                renderer.echo(f"    rule: {block.rule_id}")

    if vm.risky_tokens:
        renderer.echo("")
        renderer.echo(f"Risky Tokens: {', '.join(vm.risky_tokens)}")

    if vm.causal_chain:
        renderer.echo("")
        chain_str = " -> ".join(
            f"{s.phase}({s.status})" if s.status else s.phase
            for s in vm.causal_chain
        )
        renderer.echo(f"Causal Chain: {chain_str}")

    if vm.next_actions:
        renderer.echo("")
        renderer.echo("Next Actions")
        for action in vm.next_actions:
            renderer.echo(f"  $ {action}")


COMMAND = ExplainCommand()
