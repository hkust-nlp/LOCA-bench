"""One line per finished episode: config, seed, outcome, steps, tool calls, calendar events
created, trims, delivered revisions, most-repeated tool, and how the episode ended.

Usage (from repo root):
    python scripts/summarize_run.py                    # most recent run in outputs/
    python scripts/summarize_run.py outputs/<run_dir>  # a specific run
"""
import json
import sys
from collections import Counter
from pathlib import Path

if len(sys.argv) > 1:
    run = Path(sys.argv[1])
else:
    runs = [p for p in Path("outputs").iterdir() if p.is_dir()]
    run = max(runs, key=lambda p: p.stat().st_mtime)
print(f"Run: {run}\n")

for traj_file in sorted(run.glob("tasks/*/state*/trajectory.json")):
    d = json.load(open(traj_file))
    task, metrics, msgs = d["task"], d["metrics"], d["messages"]

    calls = [tc["function"]["name"] for m in msgs if m.get("role") == "assistant"
             for tc in (m.get("tool_calls") or [])]
    top_tool, top_n = Counter(calls).most_common(1)[0] if calls else ("-", 0)
    creates = sum("create_event" in c for c in calls)  # 0 = never attempted the task
    trims = len(d.get("events", {}).get("trim", []))

    log = traj_file.parent / "perturbation_log.json"
    delivered = [x["id"] for x in json.load(open(log))["delivered"]] if log.exists() else []

    last = next((m for m in reversed(msgs) if m.get("role") == "assistant"), {})
    ended = "claim_done" if any("claim_done" in c for c in calls[-1:]) else \
        str(last.get("content") or "")[:70].replace("\n", " ")

    print(f"{task['config_name']:28s} seed={task['env_params'].get('seed'):<5} "
          f"acc={metrics.get('accuracy')} steps={metrics.get('total_steps'):<3} calls={len(calls):<3} "
          f"creates={creates:<3} trims={trims} revs={delivered} top={top_tool.split('_')[-1]}x{top_n} "
          f"| end: {ended}")

running = [p for p in run.glob("tasks/*/state*") if not (p / "trajectory.json").exists()]
if running:
    print(f"\n{len(running)} episode(s) still running / no trajectory yet:")
    for p in running:
        log = p / "perturbation_log.json"
        delivered = [x["id"] for x in json.load(open(log))["delivered"]] if log.exists() else []
        print(f"  {p.relative_to(run)}  revs={delivered}")