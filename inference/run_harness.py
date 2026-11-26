import asyncio
import copy
import importlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import threading
from pathlib import Path
import glob
from datetime import datetime
import fire
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from gem.tools.mcp_server.config_loader import build_server_config
from inference.common import (
    attach_conversation, attach_metrics, attach_provider_payload, build_task_workspace,
    make_base_envelope, write_all_trajectories_file, write_json_file, write_results_file,
    write_trajectory_file,
)

SKIP_SERVERS = {"filesystem", "python_execute"} 
USABLE_EXITS = {"completed", "timeout"}


def import_class(path):
    module, name = path.rsplit(".", 1)
    return getattr(importlib.import_module(module), name)


def fill(value, task_dir, ws):
    if isinstance(value, str):
        return value.replace("{task_workspace}", str(task_dir)).replace("{agent_workspace}", str(ws))
    return value


def build_mcp(mcp_servers, task_dir, ws):
    """LOCA's MCP server configs -> the {name: {command, args, env}} file `ours --mcp-servers` takes."""
    mcp = {}
    for name, s in copy.deepcopy(mcp_servers).items():  # build_server_config edits params in place
        if not s.get("enabled", True) or s["type"] in SKIP_SERVERS:
            continue
        p = {k: fill(v, task_dir, ws) for k, v in s.get("params", {}).items()}
        p |= {"task_workspace": str(task_dir), "agent_workspace": str(ws)}
        e = build_server_config(s["type"], p, name)[name]
        if e["command"] == "python":
            e["command"] = sys.executable
        e["env"] = {**e.get("env", {}), "PATH": os.environ["PATH"], "LOCA_QUIET": "1"}
        mcp[name] = e
    return mcp


async def _list_tools(e):
    params = StdioServerParameters(command=e["command"], args=e["args"], env=e["env"], cwd=e.get("cwd"))
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        return [t.name for t in (await session.list_tools()).tools]


def preflight(mcp, timeout=30):
    """Start each server and list its tools, so a broken server fails here instead of inside a run."""
    tools = {}
    for name, e in mcp.items():
        try:
            tools[name] = asyncio.run(asyncio.wait_for(_list_tools(e), timeout))
        except Exception as ex:
            raise RuntimeError(f"MCP server '{name}' failed preflight: {ex!r}") from ex
    return tools

def watch_follow_ups(runs_root, before, follow_ups, env, stop, seen, errors):
    """Call env.on_revision_delivered() as soon as `ours` sends each follow-up.

    A follow-up counts as sent once its text shows up in either place, whichever is first:
    trace/user_*/message.md (live under --harness codex, written only at the end by
    codex-shipped) or Codex's own session log harness/codex_home/sessions/**/rollout-*.jsonl,
    which Codex appends to during the run under either harness.
    """
    norm = lambda s: " ".join(s.split())
    escaped = {r["id"]: json.dumps(r["message"], ensure_ascii=False)[1:-1] for r in follow_ups}
    offsets, carry = {}, {}

    def new_rollout_text(run_dir):
        parts = []
        pattern = str(run_dir / "harness" / "codex_home" / "sessions" / "**" / "rollout-*.jsonl")
        for p in glob.glob(pattern, recursive=True):
            with open(p, "rb") as f:
                f.seek(offsets.get(p, 0))
                chunk = f.read()
            offsets[p] = offsets.get(p, 0) + len(chunk)
            text = carry.get(p, "") + chunk.decode("utf-8", errors="replace")
            carry[p] = text[-4000:]  # so a message split across two reads is still found
            parts.append(text)
        return "\n".join(parts)

    pending, run_dir = list(follow_ups), None
    while pending:
        last = stop.is_set()  # one final scan after ours exits
        try:
            if run_dir is None and runs_root.exists():
                run_dir = next((p for p in runs_root.iterdir() if p.is_dir() and p not in before), None)
            if run_dir is not None:
                rollout = new_rollout_text(run_dir)
                texts = []
                for p in run_dir.glob("trace/user_*/message.md"):
                    try:
                        texts.append(norm(p.read_text(errors="replace")))
                    except OSError:
                        pass  # being written; next poll
                trace = "\n".join(texts)
                for r in [r for r in pending if escaped[r["id"]] in rollout or norm(r["message"]) in trace]:
                    env.on_revision_delivered(r["id"])
                    seen.append({"id": r["id"], "t": time.time(), "after_exit": last})
                    pending.remove(r)
        except Exception:
            errors.append(traceback.format_exc())
            return
        if last:
            return
        stop.wait(0.2)

def first_tool_call_times(run_dir, follow_ups):
    """For each follow-up id: when the agent made its first tool call after receiving it
    (epoch seconds, from the line timestamps in Codex's session log)."""
    keys = [(r["id"], json.dumps(r["message"], ensure_ascii=False)[1:-1]) for r in follow_ups]
    out, k, current = {}, 0, None
    pattern = str(run_dir / "harness" / "codex_home" / "sessions" / "**" / "rollout-*.jsonl")
    for p in sorted(glob.glob(pattern, recursive=True)):
        for line in open(p, errors="replace"):
            if k < len(keys) and keys[k][1] in line:
                current, k = keys[k][0], k + 1
                continue
            if current is None or current in out:
                continue
            try:
                o = json.loads(line)
            except ValueError:
                continue
            kind = str((o.get("payload") or {}).get("type", ""))
            if o.get("type") == "response_item" and "call" in kind and "output" not in kind and o.get("timestamp"):
                out[current] = datetime.fromisoformat(o["timestamp"].replace("Z", "+00:00")).timestamp()
    return out

def run_one(cfg, config_name, run_id, out_dir, a):
    task_dir = build_task_workspace(out_dir / "tasks", config_name, 0, run_id)
    ws = task_dir / "agent_workspace"
    sealed = out_dir / ".sealed" / config_name / f"state{run_id}"
    runs_root = out_dir / "ours_runs" / config_name / f"state{run_id}"

    # 1. Environment. reset() wipes and regenerates task_dir, so nothing goes in it before this.
    params = {k: fill(v, task_dir, ws) for k, v in cfg["env_params"].items()}
    params.setdefault("task_dir", str(task_dir))
    env = import_class(cfg["env_class"])(**params)
    user_prompt, _ = env.reset()
    if cfg.get("prompt_prefix"):
        user_prompt = f"{cfg['prompt_prefix']} {user_prompt}"

    revs = (getattr(env, "perturbations", None) or cfg["env_params"].get("perturbations") or {}).get("revisions", [])
    follow_ups = [r for r in revs if r.get("trigger") == "on_finish"]
    if any("step" in r for r in revs):
        print("  warning: step revisions are not delivered yet")

    # 2. MCP servers, checked before a run is spent on them.
    sealed.mkdir(parents=True, exist_ok=True)
    mcp = build_mcp(cfg["mcp_servers"], task_dir, ws)
    step_revs = [r for r in revs if "step" in r]
    if step_revs:
        schedule_file = sealed / "step_revisions.json"
        schedule_file.write_text(json.dumps(step_revs))
        mcp = wrap_with_proxy(mcp, schedule_file, task_dir / "perturbation_log.json", sealed / "mcp_calls")
    tools = preflight(mcp)
    mcp_file = sealed / "mcp.json"
    mcp_file.write_text(json.dumps(mcp, indent=2))

    # 3. Run, with the answer key moved out of task_dir (Codex's shell can read anywhere).
    cmd = [a["ours_bin"], "run", "--harness", a["harness"], "--model", a["model"],
           "--context-window", str(a["context_window"]), "--lane", a["lane"],
           "--reasoning-effort", a["reasoning_effort"], "--wall-clock-s", str(a["wall_clock_s"]),
           "--task", f"{config_name}_state{run_id}", "--prompt", user_prompt,
           "--seed", str(ws), "--mcp-servers", str(mcp_file), "--runs-root", str(runs_root)]

    if a["harness"] == "codex":  # codex-shipped has no model-info flags and only the subscription lane
        cmd += ["--model-info-dir", str(Path(a["model_info_dir"]).resolve())]
    for r in follow_ups:
        cmd += ["--follow-up", r["message"]]
    gt, gt_sealed = task_dir / "groundtruth_workspace", sealed / "groundtruth_workspace"
    before = set(runs_root.iterdir()) if runs_root.exists() else set()
    stop, seen, errors = threading.Event(), [], []
    watcher = threading.Thread(target=watch_follow_ups, daemon=True,
                               args=(runs_root, before, follow_ups, env, stop, seen, errors))
    shutil.move(gt, gt_sealed)
    try:
        (task_dir / "logs").mkdir(exist_ok=True)
        with open(task_dir / "logs" / "ours.log", "w") as log:
            proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
            watcher.start()
            try:
                proc.wait(timeout=a["wall_clock_s"] + 900)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                raise
    finally:
        stop.set()
        if watcher.is_alive():
            watcher.join(timeout=10)
        shutil.move(gt_sealed, gt)

    # 4. What happened.
    run_dir = max(runs_root.iterdir(), key=lambda p: p.stat().st_mtime)
    run = json.loads((run_dir / "run.json").read_text())
    shutil.copytree(run_dir / "workspace", ws, dirs_exist_ok=True)  # evaluators read agent files here

    # Follow-up i went out as turn i+2 (turn 1 is the prompt); a listed turn is a delivered one.
    n_turns = len(run.get("turns", []))
    delivered = [{"id": r["id"], "step": i + 2, "channel": "user_turn"}
                 for i, r in enumerate(follow_ups) if i + 2 <= n_turns]
    turn_ids = [d["id"] for d in delivered]
        # How long after the start of the turn it opened was each follow-up detected?
    starts = {}
    for d in delivered:  # follow-up i opened turn i+2
        started = run["turns"][d["step"] - 1].get("started")
        if started:
            starts[d["id"]] = datetime.fromisoformat(started.replace("Z", "+00:00")).timestamp()
    for s in seen:
        if s["id"] in starts:
            s["lag_s"] = round(s["t"] - starts[s["id"]], 1)
    if revs:
        log_file = task_dir / "perturbation_log.json"
        prior = json.loads(log_file.read_text())["delivered"] if log_file.exists() else []
        delivered = prior + delivered
        write_json_file(log_file, {"delivered": delivered})

    # 5. Score with LOCA's own evaluator.
    _, reward, _, _, info = env.step("claim_done")

    problems = []
    if run.get("exit_reason") not in USABLE_EXITS:
        problems.append(f"exit_reason={run.get('exit_reason')}: {str(run.get('exit_detail'))[:300]}")
    if run.get("token_counter") == "len/4":
        problems.append("token_counter=len/4: tiktoken didn't load, so budgets were off")
    if errors:
        problems.append("follow-up watcher crashed: " + errors[0][-400:])
    if sorted(s["id"] for s in seen) != sorted(turn_ids):
        problems.append(f"watcher saw follow-ups {[s['id'] for s in seen]} but run.json has {turn_ids}")
    late = [s for s in seen if s["after_exit"] or not -2 <= s.get("lag_s", 0) <= 5]
    first_call = first_tool_call_times(run_dir, follow_ups)
    for s in seen:
        if s["id"] in first_call:
            s["margin_s"] = round(first_call[s["id"]] - s["t"], 1)  # > 0: applied before the agent acted
    late = [s for s in seen if s["after_exit"] or s.get("margin_s", 1) <= 0]
    if late:
        problems.append("follow-up side effects applied after the agent's first tool call in that turn: " + ", ".join(
            f"{s['id']} margin={s.get('margin_s')}s after_exit={s['after_exit']}" for s in late))
    status = "invalid" if problems else "success"
    steps = run.get("trace", {}).get("steps", 0)
    commit = run.get("code", {}).get("commit")

    write_json_file(task_dir / "eval.json", {
        "status": status, "accuracy": reward, "steps": steps, "feedback": str(info),
        "problems": problems, "delivered": [d["id"] for d in delivered],
        "ours_exit": run.get("exit_reason"), "ours_commit": commit, "ours_run_dir": str(run_dir), 'injected': seen})

    traj = make_base_envelope("ours", task={"config_name": config_name, "run_id": run_id,
                                            "env_class": cfg["env_class"], "env_params": cfg["env_params"]})
    attach_conversation(traj, user_prompt=user_prompt, follow_ups=[r["message"] for r in follow_ups])
    attach_metrics(traj, accuracy=reward, total_steps=steps, completed=run.get("exit_reason") == "completed")
    attach_provider_payload(traj, run_dir=str(run_dir), run=run, mcp_tools=tools)
    write_trajectory_file(task_dir / "trajectory.json", traj, legacy_payload={"messages": []})

    return {"config_name": config_name, "run_id": run_id, "status": status,
            "accuracy": reward, "steps": steps, "commit": commit}


def main(config_file, model, context_window, model_info_dir="model_info", lane="subscription",
         harness="codex", reasoning_effort="medium", wall_clock_s=3600, ours_bin="ours", output_dir=None):
    a = dict(model=model, context_window=context_window, model_info_dir=model_info_dir, lane=lane,
             harness=harness, reasoning_effort=reasoning_effort, wall_clock_s=wall_clock_s, ours_bin=ours_bin)
    configs = json.load(open(config_file))["configurations"]
    stamp = time.strftime("%Y%m%d_%H%M%S")
    default_dir = f"outputs/inf_ours-{harness}_{Path(config_file).stem}_{model.replace('/', '-')}_CW{context_window}_{stamp}"
    out_dir = Path(output_dir or default_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Configs sharing a name are seeds of one task: state0, state1, ... in file order.
    jobs, counts = [], {}
    for cfg in configs:
        name = cfg.get("name") or cfg["env_class"].rsplit(".", 1)[-1]
        jobs.append((cfg, name, counts.get(name, 0)))
        counts[name] = counts.get(name, 0) + 1

    results = []
    for cfg, name, run_id in jobs:
        print(f"[{name}/state{run_id}] seed={cfg['env_params'].get('seed')}")
        try:
            r = run_one(cfg, name, run_id, out_dir, a)
        except Exception:
            tb = traceback.format_exc()
            print(tb)
            task_dir = build_task_workspace(out_dir / "tasks", name, 0, run_id)
            write_json_file(task_dir / "eval.json", {"status": "error", "accuracy": 0.0, "steps": 0, "feedback": tb})
            r = {"config_name": name, "run_id": run_id, "status": "error", "accuracy": 0.0, "steps": 0, "commit": None}
        print(f"  -> {r['status']} accuracy={r['accuracy']}")
        results.append(r)

    ok = [r for r in results if r["status"] == "success"]
    per_config = {}
    for name, total in counts.items():
        rs = [r for r in ok if r["config_name"] == name]
        per_config[name] = {"success": len(rs), "total": total, "accuracies": [r["accuracy"] for r in rs],
                            "avg_accuracy": round(sum(r["accuracy"] for r in rs) / len(rs), 4) if rs else None}
    commits = sorted({r["commit"] for r in results if r["commit"]})
    if len(commits) > 1:
        print(f"WARNING: runs used different ours builds {commits}. Pin one with `ours use TAG`.")
    write_results_file(
        out_dir / "results.json",
        metadata={"harness": harness, "model": model, "context_window": context_window, "lane": lane,
                  "reasoning_effort": reasoning_effort, "config_file": config_file, "ours_commits": commits},
        summary={"total": len(results), "success": len(ok),
                 "avg_accuracy": round(sum(r["accuracy"] for r in ok) / len(ok), 4) if ok else None},
        per_config=per_config)
    write_all_trajectories_file(out_dir / "tasks", out_dir, results)
    print(f"Results: {out_dir / 'results.json'}")


if __name__ == "__main__":
    fire.Fire(main)