from pathlib import Path
import noesis as ns
from noesis import context

# keep demo runs separate
ns.set(runs_dir="./runs/demo")

# (optional) pin planner mode; default is meta
# ns.set(planner_mode="meta")  # or "minimal" to compare

print("=== EPISODE: normal task ===")
eid_ok = ns.run("Summarize the release notes in ./CHANGELOG.md", intuition=False)
print("episode_id:", eid_ok)

print("\n=== EPISODE: dangerous goal triggers pre-act veto ===")
eid_veto = ns.run("Danger operation: delete production database", intuition=False)
print("episode_id:", eid_veto)

print("\n=== SUMMARIES ===")
for eid in (eid_ok, eid_veto):
    s = ns.summary.read(eid)
    print(f"- {eid}: success={s['metrics']['success']} | insight={s['insight']['metrics']}")
