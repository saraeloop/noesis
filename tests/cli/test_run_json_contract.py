from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

import noesis as ns
from noesis.cli import main as cli_main


@contextmanager
def _preserve_config():
    snapshot = ns.get()
    try:
        yield
    finally:
        ns.set(**snapshot)


def _assert_artifacts_exist(episode_dir: Path, artifacts: dict[str, str]) -> None:
    for rel in artifacts.values():
        path = episode_dir / rel
        assert path.exists(), f"missing artifact: {path}"


def test_run_json_envelope_and_artifacts(tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))

        code = cli_main(["run", "json contract test", "--json"])
        captured = capsys.readouterr()
        out = captured.out.strip()
        err = captured.err

        assert code == 0
        assert err == ""
        lines = out.splitlines()
        assert len(lines) == 1
        payload = json.loads(lines[0])

        cli = payload["cli"]
        assert cli["schema_version"] == "cli/1.0"
        assert cli["compat_min"] == "cli/1.0"
        assert cli["compat_max"] == "cli/1.x"

        episode_dir = Path(payload["episode_dir"])
        assert episode_dir.is_absolute()
        assert episode_dir.exists()

        artifacts = payload["artifacts"]
        assert "summary" in artifacts
        assert "manifest" in artifacts
        _assert_artifacts_exist(episode_dir, artifacts)

        assert payload["outcome"] in {"success", "success_unverified", "goal_not_achieved", "error"}
        assert payload["adapter_result"] in {"success", "error", "skipped"}

        capabilities = payload["capabilities"]
        assert "verification" in capabilities
        assert payload["invocation"]["verify_provided"] is False


def test_run_json_cli_version_forward(tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))

        code = cli_main(["run", "version test", "--json", "--cli-version", "cli/1.5"])
        captured = capsys.readouterr()
        out = captured.out.strip()
        err = captured.err

        assert code == 0
        assert err == ""
        payload = json.loads(out)
        assert payload["cli"]["schema_version"] == "cli/1.0"


def test_run_json_cli_version_invalid(tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))

        code = cli_main(["run", "bad version", "--json", "--cli-version", "1.0"])
        captured = capsys.readouterr()
        out = captured.out.strip()
        err = captured.err

        assert code == 2
        assert out == ""
        assert "invalid cli version" in err


def test_run_json_cli_version_unsupported(tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))

        code = cli_main(["run", "bad major", "--json", "--cli-version", "cli/2.0"])
        captured = capsys.readouterr()
        out = captured.out.strip()
        err = captured.err

        assert code == 3
        assert out == ""
        assert "unsupported cli version" in err
