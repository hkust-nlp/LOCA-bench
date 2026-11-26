"""Summarize ours batches by harness and variant.

Usage (from repo root):
    python compare.py outputs/<run1> outputs/<run2> ...
"""
import contextlib
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

from diag import diagnose

rows = defaultdict(list)
for run in map(Path, sys.argv[1:]):
    harness = run.name.split("_")[1].removeprefix("ours-")  # inf_ours-<harness>_<config>_...
    for state in sorted(run.glob("tasks/*/state*")):
        f = state / "eval.json"
        if not f.exists():
            continue
        ev = json.loads(f.read_text())
        r = {"status": ev.get("status"), "acc": ev.get("accuracy", 0.0), "steps": ev.get("steps", 0),
             "deliv": len(ev.get("delivered") or []), "conf": None, "checks": {}}
        if r["status"] == "success":
            with contextlib.redirect_stdout(io.StringIO()):
                n_ok, n, r["checks"] = diagnose(state)
            r["conf"] = n_ok / n
        rows[(harness, state.parent.name)].append(r)

mean = lambda xs: sum(xs) / len(xs) if xs else float("nan")
rate = lambda rs, k: mean([ok for r in rs for kind, ok in r["checks"].values() if kind == k])
print(f"{'harness':16s} {'variant':28s} {'n':>3s} {'invalid':>7s} {'deliv':>5s} {'solved':>7s} "
      f"{'conf ok':>8s} {'fact ok':>8s} {'exc ok':>7s} {'ext ok':>7s} {'steps':>6s}")
for (h, v), rs in sorted(rows.items()):
    ok = [r for r in rs if r["status"] == "success"]
    print(f"{h:16s} {v:28s} {len(rs):3d} {len(rs) - len(ok):7d} {mean([r['deliv'] for r in ok]):5.1f} "
          f"{mean([r['acc'] for r in ok]):7.2f} {mean([r['conf'] for r in ok]):8.2f} {rate(ok, 'fact'):8.2f} "
          f"{rate(ok, 'exception'):7.2f} {rate(ok, 'extended'):7.2f} {mean([r['steps'] for r in ok]):6.0f}")