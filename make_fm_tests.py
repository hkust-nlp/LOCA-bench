"""
Usage: python make_fm_tests.py 64k
"""
import copy
import json
import sys
from datetime import datetime
SIZE = sys.argv[1] if len(sys.argv) > 1 else "64k"
SEEDS = [42, 123, 456, 789, 2024]
SOURCE = f"task-configs/final_{SIZE}_set_config.json"
OUT = f"task-configs/fm_tests_{SIZE}.json"

# Same follow-up format as make_pair.py, but each variant gets its own short list so that two
# variants of the same failure mode differ in exactly one message:
#   fm1_* : with vs without noise before the wipe (context dropped)
#   fm2_* : the same moved deadline, announced clearly / vaguely / not at all (never rechecks)
#   fm3_* : the same change worded clearly vs ambiguously (misreads the change)
B1 = {"id": "b1", "trigger": "on_finish", "delta_hours": 1, "salience": "explicit",
      "message": "Change of plans, set all the camera-ready reminders 1 hour earlier than the note says."}
B2 = {"id": "b2", "trigger": "on_finish", "delta_hours": 2, "salience": "explicit",
      "message": "Give me 2 more hours of buffer on all of those reminders, so move them 2 hours earlier."}
B3 = {"id": "b3", "trigger": "on_finish", "delta_hours": 4, "salience": "explicit",
      "message": "Sorry, one more. Move every camera-ready reminder a further 4 hours earlier than where they are now."}
N1 = {"id": "n1", "kind": "noise", "trigger": "on_finish", "salience": "offhand",
      "message": "Unrelated, but before I forget: can you go through every workshop, registration and general "
                 "conference update email and quote me exactly what each one says, word for word? I want to "
                 "skim them all in one place."}
W1 = {"id": "w1", "kind": "wipe", "trigger": "on_finish", "salience": "explicit",
      "delete_subjects": ["Camera-Ready Deadline EXTENDED", "REMINDER: Camera-Ready Deadline"],
      "wipe_calendar": True,
      "message": "Ugh, my mail client flagged a bunch of the conference emails as spam and deleted them, and most "
                 "of my calendar got wiped too. Can you put the missing camera-ready reminders back exactly the "
                 "way they were, from what you already know?"}

VARIANTS = {
    "fm1_wipe_noise": [B1, N1, W1, B3],
    "fm1_wipe_clean": [B1, W1, B3],
    "fm1_noise_only": [B1, N1, B3],
    "fm2_explicit": [{"id": "f1", "kind": "fact", "trigger": "on_finish", "shift_days": 2, "salience": "explicit",
                      "message": "Hey, I think one of the camera-ready deadlines changed since you set these. Can you "
                                 "go back through the emails, find the latest deadline for each conference, and update "
                                 "any reminder whose deadline moved?"}],
    "fm2_vague": [{"id": "f1", "kind": "fact", "trigger": "on_finish", "shift_days": 2, "salience": "offhand",
                   "message": "I think a deadline might have moved, not sure which one."}],
    "fm2_silent": [{"id": "f1", "kind": "fact", "trigger": "on_finish", "shift_days": 2, "salience": "offhand",
                    "message": "Thanks! Can you double-check that everything is set up correctly before you finish?"}],
    "fm3_dir_clear": [dict(B2, message="Move all the camera-ready reminders 2 hours earlier.")],
    "fm3_dir_ambiguous": [dict(B2, message="Push all the camera-ready reminders back 2 hours.")],
    "fm3_undo_by_value": [B1, B2, {"id": "u1", "kind": "undo", "undoes": "b1", "trigger": "on_finish",
                                   "salience": "explicit",
                                   "message": "Actually, undo the 1-hour change but keep the 2-hour one."}],
    "fm3_undo_by_order": [B1, B2, {"id": "u1", "kind": "undo", "undoes": "b1", "trigger": "on_finish",
                                   "salience": "offhand",
                                   "message": "Actually wait, undo the first change you made but keep the second."}],
}
for name, revs in VARIANTS.items():
    msgs = [r["message"] for r in revs]
    assert all(m == " ".join(m.split()) for m in msgs), "follow-up texts must be single-line and single-spaced"
    assert len(set(msgs)) == len(msgs) and not any(a != b and a in b for a in msgs for b in msgs), \
        "follow-up texts must be distinct and not contain each other (the ours watcher matches on text)"
    ids = [r["id"] for r in revs]
    for r in revs:
        if r.get("kind") == "undo":
            target = revs[ids.index(r["undoes"])]
            assert target.get("kind", "buffer") == "buffer" and ids.index(target["id"]) < ids.index(r["id"]), name

base = {c["env_params"]["seed"]: c
        for c in json.load(open(SOURCE))["configurations"] if c["name"] == "SetConfCrDdlS2LEnv"}

configs = []
for name, revs in VARIANTS.items():
    for seed in SEEDS:
        cfg = copy.deepcopy(base[seed])
        cfg["name"] = f"SetConfCrDdl{SIZE}_{name}"
        cfg["env_params"]["perturbations"] = {"base_offset_hours": 3, "revisions": copy.deepcopy(revs)}
        # python_execute isn't sandboxed: it can read ../groundtruth_workspace (answer key and
        # future revisions) and dump the raw databases. This task doesn't need it.
        today = datetime.strptime(cfg["env_params"]["base_date"], "%Y-%m-%d")
        cfg["prompt_prefix"] = today.strftime("Today is %A, %B %-d, %Y.")  # "Today is Monday, September 15, 2025."
        cfg["mcp_servers"]["python_execute"]["enabled"] = False
        configs.append(cfg)

json.dump({"configurations": configs}, open(OUT, "w"), indent=2)
print(f"Wrote {len(configs)} configs ({len(VARIANTS)} variants x {len(SEEDS)} seeds) to {OUT}")
