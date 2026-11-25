"""Diagnose perturbed SetConfCrDdl episodes: for each target conference, find the agent's
reminder events, compute the offset it actually used, and decode which revisions it applied
(deltas are powers of two, so every subset of applied revisions gives a unique offset).

Usage (from repo root):
    PYTHONPATH=. python scripts/diagnose_perturbation.py                   # failed perturbed episodes, most recent run
    PYTHONPATH=. python scripts/diagnose_perturbation.py --all             # all perturbed episodes, most recent run
    PYTHONPATH=. python scripts/diagnose_perturbation.py outputs/<run>     # failed perturbed episodes in that run
    PYTHONPATH=. python scripts/diagnose_perturbation.py <.../state0>      # one episode
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from mcp_convert.mcps.calendar.database_utils import CalendarDatabase


def diagnose(task):
    gt = task / "groundtruth_workspace"
    p = gt / "perturbations.json"
    schedule = json.load(open(p)) if p.exists() else {}
    base = schedule.get("base_offset_hours", 3)
    revs = {r["id"]: r for r in schedule.get("revisions", [])}
    log_file = task / "perturbation_log.json"
    delivered_ids = [d["id"] for d in json.load(open(log_file))["delivered"]] if log_file.exists() else []
    kind = lambda i: revs[i].get("kind", "buffer")
    buffers = [i for i in delivered_ids if kind(i) == "buffer"]
    facts = {revs[i]["conference"]: revs[i] for i in delivered_ids if kind(i) == "fact"}
    confs = json.load(open(gt / "conference_metadata.json"))["target_info"]["conferences"]
    receiver = json.load(open(task / "email_config.json"))["email"]
    inbox = json.load(open(task / "local_db" / "emails" / "users_data" / receiver / "emails.json"))
    original = {}  # deadline in each conference's first notice ("Submission Instructions" emails survive the wipe)
    for e in inbox.values():
        parts = e["id"].split("_")
        m = re.search(r"Deadline: (\S+)", e.get("body", ""))
        if parts[0] == "email" and "Submission Instructions" in e.get("subject", "") and m:
            original[parts[1]] = m.group(1)
    # Which buffer revisions each conference's reminder should include (mirrors the evaluator).
    want, frozen = {c["conference"]: set() for c in confs}, {}
    for i in delivered_ids:
        if kind(i) == "exception":
            frozen[revs[i]["conference"]] = i
        for c, s in want.items():
            if c in frozen:
                continue
            if kind(i) == "buffer":
                s.add(i)
            elif kind(i) == "undo":
                s.discard(revs[i]["undoes"])
    hours = lambda ids: base + sum(revs[i]["delta_hours"] for i in ids)

    print(f"Delivered: {delivered_ids} of {list(revs)}")
    missing = [i for i in revs if i not in delivered_ids]
    if missing:
        print(f"  !! never delivered: {missing}  (agent finished first or ran out of time)")
    for i in delivered_ids:
        r = revs[i]
        if kind(i) == "fact":
            print(f"  fact {i}: {r['conference']} deadline {r['old_deadline']} -> {r['new_deadline']}"
                  f"  (email dated {r['email']['date']}, buried={r['buried']})")
        elif kind(i) == "exception":
            print(f"  exception {i}: leave {r['conference']} alone from here on")
        elif kind(i) == "undo":
            print(f"  undo {i}: reverses {r['undoes']}")
        elif kind(i) == "wipe":
            print(f"  wipe {i}: deleted {r.get('delete_subjects')}, calendar wiped={r.get('wipe_calendar')}")
    print()

    def decode(offset_h):
        """Which delivered buffer revisions sum to (offset - base)? None if no subset matches."""
        extra = round(offset_h - base)
        applied = [i for i in buffers if extra & revs[i]["delta_hours"]]
        return applied if sum(revs[i]["delta_hours"] for i in applied) == extra else None

    def hours_before(deadline, start):
        return (datetime.fromisoformat(deadline) - start).total_seconds() / 3600

    events = CalendarDatabase(data_dir=str(task / "local_db" / "calendar")).list_events(
        time_min="2000-01-01T00:00:00Z", time_max="2100-01-01T00:00:00Z")

    n_ok, checks = 0, {}
    n_ok, checks = 0, {}
    for c in confs:
        key = c["conference"]
        fact = facts.get(key)
        target = fact["new_deadline"] if fact else c["deadline"]
        extended = original.get(key, target) != target  # the right deadline differs from the first notice
        expected = hours(want[key])
        tags = ([f"fact {fact['id']}"] if fact else []) + ([f"exception {frozen[key]}"] if key in frozen else []) \
            + (["extended"] if extended else [])
        tag = f" [{', '.join(tags)}]" if tags else ""
        mine = [e for e in events if re.search(r"\b" + re.escape(key.lower()) + r"\b", e.get("summary", "").lower())]
        conf_ok = False
        if not mine:
            print(f"{key:6s} NO EVENT{tag}")
        for e in mine:
            start = datetime.fromisoformat(e["start"]["dateTime"])
            off = hours_before(target, start)
            ok = abs(off - expected) < 5 / 60
            conf_ok |= ok
            note = ""
            if not ok and fact and decode(hours_before(fact["old_deadline"], start)) is not None:
                off, note = hours_before(fact["old_deadline"], start), f" | uses the OLD deadline (missed {fact['id']})"
            elif not ok and extended and decode(hours_before(original[key], start)) is not None:
                off, note = hours_before(original[key], start), " | uses the ORIGINAL deadline (forgot the extension)"
            applied = decode(off)
            if applied is None:
                dec = "offset matches no revision subset"
            else:
                dec = f"applied {applied}"
                extra, lacking = set(applied) - want[key], want[key] - set(applied)
                if extra:
                    dec += f", should not have {sorted(extra)}"
                if lacking:
                    dec += f", missing {sorted(lacking)}"
            dup = f" (1 of {len(mine)} events)" if len(mine) > 1 else ""
            print(f"{key:6s} {'OK ' if ok else 'BAD'} offset {off:5.1f}h (want {expected}h) | {dec}{note}{dup}{tag}"
                  f" | '{e.get('summary', '')}'")
        n_ok += conf_ok
        if fact:
            checks[fact["id"]] = ("fact", conf_ok)
        if key in frozen:
            checks[frozen[key]] = ("exception", conf_ok)
        if extended:
            checks[f"ext:{key}"] = ("extended", conf_ok)

    print(f"\n{n_ok}/{len(confs)} conferences have a correct reminder")
    return n_ok, len(confs), checks


args = [a for a in sys.argv[1:] if not a.startswith("--")]
show_all = "--all" in sys.argv

if args and (Path(args[0]) / "groundtruth_workspace").exists():
    episodes = [Path(args[0])]  # a single episode folder
else:
    if args:
        run = Path(args[0])
    else:
        run = max((p for p in Path("outputs").iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
    print(f"Run: {run}")
    episodes = []
    for state in sorted(run.glob("tasks/*/state*")):
        traj = state / "trajectory.json"
        if not (state / "groundtruth_workspace" / "perturbations.json").exists():
            continue  # vanilla episode
        if not traj.exists():
            print(f"  (skipping {state.relative_to(run)}: still running)")
            continue
        if show_all or json.load(open(traj))["metrics"].get("accuracy") != 1.0:
            episodes.append(state)
    print(f"{len(episodes)} {'perturbed' if show_all else 'failed perturbed'} episode(s)")

for ep in episodes:
    print("\n" + "=" * 90 + f"\n{ep}\n" + "=" * 90)
    diagnose(ep)