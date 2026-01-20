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

        run_code = cli_main(["run", "process test", "--json", "--process", "alpha"])
        assert run_code == 0
        capsys.readouterr()

        from noesis.runtime.paths import resolve_noesis_paths

        layout = resolve_noesis_paths(workspace=None, runs_dir=runs_dir)
        episode_dirs = list(layout.episodes_dir.glob("ep_*"))
        assert len(episode_dirs) == 1
        episode_id = episode_dirs[0].name

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

        runs_code = cli_main(["runs", "--process", "alpha", "--json"])
        captured = capsys.readouterr()
        assert runs_code == 0
        rows = json.loads(captured.out.strip())
        assert any(row.get("episode_id") == episode_id for row in rows)
