from __future__ import annotations

from common.console import headline, info, success, warn, error
from common.config import load_dotenv_if_present, require_openai_key, import_noesis
from common.episode_io import episode_dir, read_events_jsonl, read_summary_json, summarize_timeline
from common.errors import QuickstartError


def main() -> int:
    headline("Hello Episode — See Your Agent Think")

    try:
        load_dotenv_if_present()
        require_openai_key()

        ns = import_noesis()

        task = "Summarize why tracing agent steps matters in production."
        info(f"Task: {task}")

        # Noesis API path 
        episode_id = ns.run(task, intuition=True)
        success(f"Episode ID: {episode_id}")

        # Your repo’s README says runs are under ./runs by default.
        # If you want a fixed label, set it explicitly:
        # ns.set(runs_dir="./runs/demo")

        runs_dir = "runs"  # repo-root relative
        ep_dir = episode_dir(runs_dir, episode_id)
        success(f"Episode folder: {ep_dir}")

        events = read_events_jsonl(runs_dir=runs_dir, episode_id=episode_id, limit=30)
        summary = read_summary_json(runs_dir=runs_dir, episode_id=episode_id)

        headline("Timeline (first events)")
        for verb, status in summarize_timeline(events, limit=20):
            print(f"[{verb:<12}] {status}")

        headline("Summary (best-effort)")
        metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
        if metrics:
            for k in ("success", "status", "total_ms", "tokens"):
                if k in metrics:
                    print(f"{k}: {metrics.get(k)}")
        else:
            for k in ("status", "success", "summary", "reasons"):
                if k in summary:
                    print(f"{k}: {summary.get(k)}")

        info(f"Tip: run `noesis view {episode_id}` for the full humanized timeline.")
        success("Hello Episode completed.")
        return 0

    except QuickstartError as e:
        error(str(e))
        return 2
    except Exception as e:
        error(f"Unexpected failure: {e}")
        warn("If artifacts weren’t found, confirm where Noēsis is writing runs (runs_dir + label).")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())