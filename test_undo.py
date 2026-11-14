import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from gem.envs.set_conf_cr_ddl_s2l.set_conf_cr_ddl_s2l import SetConfCrDdlS2LEnv
from mcp_convert.mcps.calendar.database_utils import CalendarDatabase

cfg = json.load(open("task-configs/perturb_pair_64k.json"))["configurations"][1]
assert cfg["name"].endswith("_perturbed") and cfg["env_params"]["seed"] == 42


def score(label, hours):  # hours(is_exception_conf) -> reminder offset used for every conference
    task = Path(tempfile.mkdtemp()) / "task"
    env = SetConfCrDdlS2LEnv(**{**cfg["env_params"], "task_dir": str(task)})
    revs = env.perturbations["revisions"]
    for r in revs:
        env.on_revision_delivered(r["id"])
    (task / "perturbation_log.json").write_text(json.dumps({"delivered": [
        {"id": r["id"], "step": i + 2, "channel": "user_turn"} for i, r in enumerate(revs)]}))
    frozen = {r["conference"] for r in revs if r.get("kind") == "exception"}
    moved = {r["conference"]: r["new_deadline"] for r in revs if r.get("kind") == "fact"}
    cal = CalendarDatabase(data_dir=str(task / "local_db" / "calendar"))
    meta = json.loads((task / "groundtruth_workspace" / "conference_metadata.json").read_text())
    for c in meta["target_info"]["conferences"]:
        key = c["conference"]
        start = datetime.fromisoformat(moved.get(key, c["deadline"])) - timedelta(hours=hours(key in frozen))
        cal.create_event({"summary": f"{key} camera ready reminder", "start": {"dateTime": start.isoformat()},
                          "end": {"dateTime": (start + timedelta(minutes=30)).isoformat()}})
    print(f"{label}: {env.step('claim_done')[1]}   {task}")
    return revs


revs = score("correct: exception 3h, others 9h  (expect 1.0)", lambda x: 3 if x else 9)
score("ignored the undo: others 10h       (expect 0.0)", lambda x: 3 if x else 10)
score("undid b2 instead of b1: others 8h  (expect 0.0)", lambda x: 3 if x else 8)
score("ignored the exception: all 9h      (expect 0.0)", lambda x: 9)
print("\nx1 message:", next(r["message"] for r in revs if r["id"] == "x1"))
print("fact confs:", [r["conference"] for r in revs if r.get("kind") == "fact"],
      "| exception conf:", [r["conference"] for r in revs if r.get("kind") == "exception"])