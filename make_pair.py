"""
Usage: python make_pair.py 64k
"""
import copy
import json
import sys
from datetime import datetime
SIZE = sys.argv[1] if len(sys.argv) > 1 else "64k"
SEEDS = [42, 123, 456, 789, 2024]
SOURCE = f"task-configs/final_{SIZE}_set_config.json"
OUT = f"task-configs/perturb_pair_{SIZE}.json"

# Every revision is a follow-up sent when the agent says it's done. Buffer deltas are distinct
# powers of two so diag.py can tell which ones the agent applied. Fact revisions add a buried
# "deadline EXTENDED" email for a conference the env picks (a different one per revision).
PERTURBATIONS = {
    "base_offset_hours": 3,
    "revisions": [
        {"id": "x1", "kind": "exception", "trigger": "on_finish", "salience": "explicit",
         "message": "Oh, one thing, leave the {conference} reminder alone from now on. I'll handle that one "
                    "myself, so don't change it whatever else I ask."},
        {"id": "b1", "trigger": "on_finish", "delta_hours": 1, "salience": "explicit",
         "message": "Change of plans, set all the camera-ready reminders 1 hour earlier than the note says."},
        {"id": "f1", "kind": "fact", "trigger": "on_finish", "shift_days": 2, "salience": "explicit",
         "message": "Hey, I think one of the camera-ready deadlines changed since you set these. Can you go back "
                    "through the emails, find the latest deadline for each conference, and update any reminder "
                    "whose deadline moved?"},
        {"id": "b2", "trigger": "on_finish", "delta_hours": 2, "salience": "offhand",
         "message": "My schedules getting really packed. Give me another 2 hours of buffer on all of those reminders."},
        {"id": "u1", "kind": "undo", "undoes": "b1", "trigger": "on_finish", "salience": "offhand",
         "message": "Actually wait, some meetings got cancelled. Undo the first time I asked you to move "
                    "the reminders earlier, but keep the second one."},
        {"id": "f2", "kind": "fact", "trigger": "on_finish", "shift_days": 3, "salience": "offhand",
         "message": "I think another deadline moved. Can you check the emails again and update the reminder for it?"},
        {"id": "b3", "trigger": "on_finish", "delta_hours": 4, "salience": "explicit",
         "message": "Sorry, one more. Move every camera-ready reminder a further 4 hours earlier than where they are now."},
    ],
}
revs = PERTURBATIONS["revisions"]
msgs = [r["message"] for r in revs]
assert all(m == " ".join(m.split()) for m in msgs), "follow-up texts must be single-line and single-spaced"
assert len(set(msgs)) == len(msgs) and not any(a != b and a in b for a in msgs for b in msgs), \
    "follow-up texts must be distinct and not contain each other (the ours watcher matches on text)"
ids = [r["id"] for r in revs]
for r in revs:
    if r.get("kind") == "undo":
        target = revs[ids.index(r["undoes"])]
        assert target.get("kind", "buffer") == "buffer" and ids.index(target["id"]) < ids.index(r["id"]), r["id"]

base = {c["env_params"]["seed"]: c
        for c in json.load(open(SOURCE))["configurations"] if c["name"] == "SetConfCrDdlS2LEnv"}

configs = []
for seed in SEEDS:
    van = copy.deepcopy(base[seed])
    van["name"] = f"SetConfCrDdl{SIZE}_vanilla"
    per = copy.deepcopy(base[seed])
    per["name"] = f"SetConfCrDdl{SIZE}_perturbed"
    per["env_params"]["perturbations"] = PERTURBATIONS
    for cfg in (van, per):
        # python_execute isn't sandboxed: it can read ../groundtruth_workspace (answer key and
        # future revisions) and dump the raw databases. This task doesn't need it.
        today = datetime.strptime(cfg["env_params"]["base_date"], "%Y-%m-%d")
        cfg["prompt_prefix"] = today.strftime("Today is %A, %B %-d, %Y.")  # "Today is Monday, September 15, 2025."
        cfg["mcp_servers"]["python_execute"]["enabled"] = False
    configs += [van, per]

json.dump({"configurations": configs}, open(OUT, "w"), indent=2)
print(f"Wrote {len(configs)} configs ({len(SEEDS)} seeds x vanilla/perturbed) to {OUT}")