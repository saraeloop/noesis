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


def test_ps_and_runs_filter_by_process(tmp_path, capsys) -> None:
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

        ps_code = cli_main(["ps", "--json"])
        captured = capsys.readouterr()
        assert ps_code == 0
        envelope = json.loads(captured.out.strip())
        processes = envelope["processes"]
        assert any(row["process_name"] == "alpha" for row in processes)

        runs_code = cli_main(["runs", "--process", "alpha", "--json"])
        captured = capsys.readouterr()
        assert runs_code == 0
        rows = json.loads(captured.out.strip())
        assert any(row.get("episode_id") == episode_id for row in rows)
