from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

from noesis.cli.commands.artifacts import COMMAND as ARTIFACTS_COMMAND
from noesis.cli.context import CLIContext, GlobalOptions
from noesis.runtime.artifacts.writer import ManifestWriter
from noesis.runtime.artifacts.signing import HMACManifestSigner


def _build_renderer():
    class _Renderer:
        def __init__(self) -> None:
            self.lines: list[str] = []
            self.data = None

        def banner(self, text: str) -> None:
            self.lines.append(text)

        def echo(self, text: str) -> None:
            self.lines.append(text)

        def json(self, data) -> None:
            self.data = data

    return _Renderer()


def _make_context(runs_dir: Path) -> CLIContext:
    snapshot = SimpleNamespace(runs_dir=runs_dir)
    runtime_ctx = SimpleNamespace(list_ports=lambda: {})
    return CLIContext(
        options=GlobalOptions(),
        config={},
        isatty=False,
        version="test",
        runtime_context=runtime_ctx,
        config_snapshot=snapshot,
        session=None,
    )


def _prepare_run(runs_dir: Path, name: str, signer: HMACManifestSigner | None = None) -> Path:
    run_dir = runs_dir / name
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text('{"ok": true}', encoding="utf-8")
    (run_dir / "state.json").write_text('{"state": "ready"}', encoding="utf-8")
    (run_dir / "events.jsonl").write_text('{"event":"start"}\n', encoding="utf-8")
    ManifestWriter(run_dir=run_dir, episode_id=name, signer=signer).finalize()
    return run_dir


def test_cli_verify_exit_codes(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    ok_run = _prepare_run(runs_dir, "ep_ok")
    missing_run = _prepare_run(runs_dir, "ep_missing")
    signature_run = _prepare_run(runs_dir, "ep_signed", signer=HMACManifestSigner(key_id="2024-Q4", secret="secret"))

    (missing_run / "events.jsonl").unlink()

    ctx = _make_context(runs_dir)

    # Success path
    renderer = _build_renderer()
    ok_args = Namespace(
        artifacts_action="verify",
        target=str(ok_run),
        strict=False,
        json=False,
        quiet=True,
    )
    assert ARTIFACTS_COMMAND.run(ok_args, ctx, renderer) == 0

    # Missing file exit code
    renderer = _build_renderer()
    missing_args = Namespace(
        artifacts_action="verify",
        target=str(missing_run),
        strict=False,
        json=False,
        quiet=True,
    )
    assert ARTIFACTS_COMMAND.run(missing_args, ctx, renderer) == 3

    # Signature issue exit code (no verifier configured)
    renderer = _build_renderer()
    sig_args = Namespace(
        artifacts_action="verify",
        target=str(signature_run),
        strict=False,
        json=False,
        quiet=True,
    )
    assert ARTIFACTS_COMMAND.run(sig_args, ctx, renderer) == 4
