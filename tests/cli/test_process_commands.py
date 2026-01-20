from __future__ import annotations

import json
from contextlib import contextmanager

import noesis as ns
from noesis.cli import main as cli_main


@contextmanager
def _preserve_config():
    snapshot = ns.get()
    try:
        yield
    finally:
        ns.set(**snapshot)


def test_processes_and_ps_filter_by_process(tmp_path, capsys) -> None:
    runs_dir = tmp_path / "runs"
    with _preserve_config():
        ns.set(runs_dir=str(runs_dir))

        alpha_code = cli_main(["run", "process alpha", "--json", "--process", "alpha"])
        assert alpha_code == 0
        capsys.readouterr()

        beta_code = cli_main(["run", "process beta", "--json", "--process", "beta"])
        assert beta_code == 0
        capsys.readouterr()

        from noesis.runtime.paths import resolve_noesis_paths

        rows = ns.list_runs(limit=10)
        alpha_rows = [row for row in rows if (row.get("process") or {}).get("name") == "alpha"]
        assert len(alpha_rows) == 1
        episode_id = alpha_rows[0]["episode_id"]

        processes_code = cli_main(["processes", "--json"])
        captured = capsys.readouterr()
        assert processes_code == 0
        envelope = json.loads(captured.out.strip())
        processes = envelope["processes"]
        assert any(row["process_name"] == "alpha" for row in processes)

        ps_code = cli_main(["ps", "--json", "--process", "alpha"])
        captured = capsys.readouterr()
        assert ps_code == 0
        ps_envelope = json.loads(captured.out.strip())
        episodes = ps_envelope["episodes"]
        assert any(row.get("episode_id") == episode_id for row in episodes)

        # Regression: limit should be applied after filtering
        ps_limited_code = cli_main(["ps", "--json", "--process", "alpha", "--limit", "1"])
        captured = capsys.readouterr()
        assert ps_limited_code == 0
        ps_limited_envelope = json.loads(captured.out.strip())
        episodes_limited = ps_limited_envelope["episodes"]
        assert len(episodes_limited) == 1
        assert episodes_limited[0].get("episode_id") == episode_id

        runs_code = cli_main(["runs", "--process", "alpha", "--json"])
        captured = capsys.readouterr()
        assert runs_code == 0
        rows = json.loads(captured.out.strip())
        assert any(row.get("episode_id") == episode_id for row in rows)
