# Standard library imports
import logging
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import copy
import json
import os
import random
from datetime import datetime, timedelta

# Local imports
from gem.core import Env
from gem.utils.constants import TERMINAL_STATE
from gem.utils.filesystem import nfs_safe_rmtree

# Constants
TASK_INSTRUCTION = '''Check my emails. The meeting information that needs to be checked is under the workspace, and there may be more than one item. Please set the corresponding reminders on the calendar as requested.'''

LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
CONSOLE_LOG_FORMAT = '%(levelname)s - %(message)s'


def _write_json_atomic(path: Path, data) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)

class SetConfCrDdlS2LEnv(Env):
    """Set Conference Camera-Ready Deadline S2L Environment for conference reminder management.
    
    This environment simulates a conference reminder scenario where the agent needs to
    check emails for camera-ready deadline notifications and set calendar reminders
    3 hours before each deadline.
    """
    
    def __init__(
        self,
        task_dir: Optional[str] = None,
        num_target: int = 1,
        num_noise: int = 2,
        noise_emails: int = 2,
        max_conferences: int = 200,
        enable_reminders: bool = True,
        enable_extensions: bool = True,
        base_date: str = '2025-09-15',
        deadline_offset: int = 15,
        seed: int = 42,
        difficulty: Optional[str] = None,
        verbose: bool = False,
        perturbations: None| dict = None,
        **_,
    ):
        """Initialize the Set Conference Camera-Ready Deadline S2L Environment.
        
        Args:
            task_dir: Directory for task-related files
            num_target: Number of target conferences with camera-ready deadlines (default: 1)
            num_noise: Number of noise conferences (default: 2)
            noise_emails: Number of emails per noise conference (default: 2)
            max_conferences: Maximum conference pool size (default: 200)
            enable_reminders: Enable reminder emails (default: True)
            enable_extensions: Enable deadline extensions (default: True)
            base_date: Base date (today) in YYYY-MM-DD format (default: 2025-09-15)
            deadline_offset: Days from base_date to deadline (default: 15)
            seed: Random seed for reproducibility
            difficulty: Difficulty preset (easy/medium/hard/expert)
            verbose: Whether to output to console
        """
        super().__init__()
        self.task_dir = task_dir
        self.verbose = verbose

        # Setup directory paths
        self.agent_workspace = Path(self.task_dir) / "agent_workspace"
        self.data_dir = Path(self.task_dir) / "local_db"
        self.email_data_dir = self.data_dir / "emails"
        self.calendar_data_dir = self.data_dir / "calendar"

        # Clear task directory if it exists, then create it
        if Path(self.task_dir).exists():
            nfs_safe_rmtree(self.task_dir)
        Path(self.data_dir).mkdir(parents=True, exist_ok=True)
        
        # Setup logging system
        self._setup_logging()

        # Configuration generation parameters
        self.num_target = num_target
        self.num_noise = num_noise
        self.noise_emails = noise_emails
        self.max_conferences = max_conferences
        self.enable_reminders = enable_reminders
        self.enable_extensions = enable_extensions
        self.base_date = base_date
        self.deadline_offset = deadline_offset
        self.seed = seed
        self.difficulty = difficulty
        self.perturbation_spec = copy.deepcopy(perturbations)
        self.perturbations = None  # resolved copy, rebuilt by every reset()

        self.reset()
    
    def _setup_logging(self) -> None:
        """Setup logging system with separate file and console handlers.
        
        Creates an independent log file for each environment instance.
        Console output is only enabled when verbose mode is active.
        """
        # Create log directory
        log_dir = Path(self.task_dir) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create logger for current instance
        self.logger = logging.getLogger(f"SetConfCrDdlS2L_{id(self)}")
        self.logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers to avoid duplication
        self.logger.handlers.clear()
        
        # File handler - records detailed logs
        log_file = log_dir / "env.log"
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Console handler - only outputs key information in verbose mode
        if self.verbose:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(CONSOLE_LOG_FORMAT)
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
        
        # Prevent log propagation
        self.logger.propagate = False
        
        self.logger.info(f"Logging system initialized, log file: {log_file}")
    
    def _get_instructions(self) -> str:
        """Get task instructions for the agent.
        
        Returns:
            str: Task instruction text
        """
        return TASK_INSTRUCTION

    def reset(self, seed: Optional[int] = None) -> Tuple[str, Dict[str, Any]]:
        """Reset environment and execute Set Conference Reminder preprocessing.
        
        Steps include:
        1. Generate conference emails with camera-ready deadlines
        2. Initialize email and calendar databases
        3. Import emails to database
        4. Copy initial workspace files to agent workspace
        5. Generate groundtruth for evaluation
        
        Args:
            seed: Random seed (optional)
        
        Returns:
            Tuple[str, Dict[str, Any]]: Task instruction and empty dictionary
        """
        super().reset(seed)
        
        try:
            # Clean and recreate task directory
            if Path(self.task_dir).exists():
                nfs_safe_rmtree(self.task_dir)
            Path(self.data_dir).mkdir(parents=True, exist_ok=True)

            # Reinitialize logging system (task_dir was deleted)
            self._setup_logging()

            self.logger.info("Starting Set Conference Reminder preprocessing...")
            self.logger.info("=" * 60)
            
            # Import preprocessing module using importlib to avoid conflicts
            try:
                import importlib.util
                env_dir = Path(__file__).parent
                preprocess_main_path = env_dir / "preprocess" / "main.py"
                
                # Load module with a unique name to avoid conflicts with other environments
                spec = importlib.util.spec_from_file_location(
                    f"set_conf_cr_ddl_s2l_{id(self)}.preprocess_main",
                    preprocess_main_path
                )
                preprocess_main_module = importlib.util.module_from_spec(spec)
                
                # Set up sys.path before loading
                sys.path.insert(0, str(env_dir / "preprocess"))
                try:
                    spec.loader.exec_module(preprocess_main_module)
                finally:
                    # Remove from sys.path after loading
                    if str(env_dir / "preprocess") in sys.path:
                        sys.path.remove(str(env_dir / "preprocess"))
                
            except ImportError as e:
                self.logger.warning(f"Could not import preprocessing module: {e}")
                self.logger.warning(f"Looked in: {env_dir}")
                return self._get_instructions(), {}
            
            # Run preprocessing
            self.logger.info("\nRunning preprocessing pipeline...")
            self.logger.info("=" * 60)
            
            # Call the preprocessing as a subprocess (without copying files)
            try:
                import subprocess
                import os

                # Set up environment variables for database directories
                env = os.environ.copy()
                env['EMAIL_DATA_DIR'] = str(self.email_data_dir)
                env['CALENDAR_DATA_DIR'] = str(self.calendar_data_dir)

                # Use preprocess/main.py from original location (not copied)
                preprocess_main = env_dir / "preprocess" / "main.py"

                # Copy necessary files to task directory
                required_files = ["email_config.json"]
                for file_name in required_files:
                    source_file = env_dir / file_name
                    if source_file.exists():
                        dest_file = Path(self.task_dir) / file_name
                        shutil.copy2(source_file, dest_file)
                        self.logger.info(f"  Copied {file_name} to task directory")

                cmd = [
                    sys.executable,
                    str(preprocess_main),
                    "--task-root", str(self.task_dir),  # Use task directory as working directory
                    "--agent_workspace", str(self.agent_workspace),
                    "--num-target", str(self.num_target),
                    "--num-noise", str(self.num_noise),
                    "--noise-emails", str(self.noise_emails),
                    "--max-conferences", str(self.max_conferences),
                    "--seed", str(self.seed),
                    "--base-date", self.base_date,
                    "--deadline-offset", str(self.deadline_offset),
                ]

                # Add flags for reminders and extensions
                if not self.enable_reminders:
                    cmd.append("--disable-reminders")

                if not self.enable_extensions:
                    cmd.append("--disable-extensions")

                # Add difficulty preset if specified
                if self.difficulty:
                    cmd.extend(["--difficulty", self.difficulty])

                # Run preprocessing with task directory as working directory
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(self.task_dir),  # Use task directory as working directory
                    env=env
                )

                if result.stdout:
                    self.logger.info(result.stdout)

                if result.returncode != 0:
                    self.logger.error("Preprocessing failed")
                    if result.stderr:
                        self.logger.error(result.stderr)
                    return self._get_instructions(), {}

                # Files are already generated in the correct locations, no need to move
                
                if self.perturbation_spec:
                    self.perturbations = copy.deepcopy(self.perturbation_spec)
                    self._resolve_fact_revisions()
                    self._resolve_exception_revisions()
                    gt_dir = Path(self.task_dir) / 'groundtruth_workspace'
                    gt_dir.mkdir(parents=True, exist_ok=True)
                    with open(gt_dir / 'perturbations.json', 'w') as f:
                        json.dump(self.perturbations, f)
                    self.logger.info("wrote perturbations to ground truth")

            except Exception as e:
                self.logger.error(f"Error running preprocessing: {e}")
                self.logger.error(traceback.format_exc())
                return self._get_instructions(), {}
            
            self.logger.info("\nSet Conference Reminder preprocessing completed!")
            self.logger.info("=" * 60)
            self.logger.info("Conference emails generated")
            self.logger.info("Email and Calendar databases initialized and populated")
            self.logger.info("Groundtruth generated")
            self.logger.info("Agent workspace ready")
            
            return self._get_instructions(), {}
            
        except Exception as e:
            self.logger.error(f"Error during preprocessing: {e}")
            self.logger.error(traceback.format_exc())
            return self._get_instructions(), {}
    
    def _organize_generated_files(self, temp_task_root: Path) -> None:
        """Organize generated files from temp directory to proper locations.
        
        Args:
            temp_task_root: Temporary task root directory where files were generated
        """
        self.logger.info("\nOrganizing generated files...")
        self.logger.info("=" * 60)
        
        try:
            # Get environment directory (code directory)
            env_dir = Path(__file__).parent
            
            # Move files directory
            temp_files = temp_task_root / "files"
            dest_files = Path(self.task_dir) / "files"
            
            if temp_files.exists():
                if dest_files.exists():
                    nfs_safe_rmtree(dest_files)
                shutil.move(str(temp_files), str(dest_files))
                self.logger.info(f"  Moved files/ to {dest_files}")
            
            # Move initial_workspace directory (if updated by preprocessing)
            temp_initial = temp_task_root / "initial_workspace"
            if temp_initial.exists():
                dest_initial = Path(self.task_dir) / "initial_workspace"
                if dest_initial.exists():
                    nfs_safe_rmtree(dest_initial)
                shutil.move(str(temp_initial), str(dest_initial))
                self.logger.info(f"  Moved initial_workspace/ to {dest_initial}")
            
            # Move groundtruth_workspace directory
            temp_groundtruth = temp_task_root / "groundtruth_workspace"
            if temp_groundtruth.exists():
                dest_groundtruth = Path(self.task_dir) / "groundtruth_workspace"
                if dest_groundtruth.exists():
                    nfs_safe_rmtree(dest_groundtruth)
                shutil.move(str(temp_groundtruth), str(dest_groundtruth))
                self.logger.info(f"  Moved groundtruth_workspace/ to {dest_groundtruth}")
            
            # Copy email_config.json from env_dir to task_dir (needed for reference)
            env_email_config = env_dir / "email_config.json"
            dest_email_config = Path(self.task_dir) / "email_config.json"
            
            if env_email_config.exists():
                shutil.copy2(str(env_email_config), str(dest_email_config))
                self.logger.info(f"  Copied email_config.json to {dest_email_config}")
            
            self.logger.info("Files organized successfully")
            
        except Exception as e:
            self.logger.warning(f"Error organizing files: {e}")
            self.logger.error(traceback.format_exc())

    def _load_email_generator(self):
        import importlib.util
        path = Path(__file__).parent / "preprocess" / "generate_conference_emails.py"
        spec = importlib.util.spec_from_file_location(f"set_conf_cr_ddl_gen_{id(self)}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Same seed and pool size as preprocessing, so conference names and organizers match.
        return module.ConferenceEmailGenerator(seed=self.seed, max_conferences=self.max_conferences)

    def _resolve_fact_revisions(self) -> None:
        """Pick a conference and build a deadline-extension email for each "fact" revision.

        Nothing is added to the inbox here; on_revision_delivered() does that when the
        follow-up goes out. Results are stored on the revision (and so in perturbations.json).
        """
        facts = [r for r in self.perturbations.get("revisions", []) if r.get("kind") == "fact"]
        if not facts:
            return
        task = Path(self.task_dir)
        meta = json.loads((task / "groundtruth_workspace" / "conference_metadata.json").read_text())
        targets = {c["conference"]: c for c in meta["target_info"]["conferences"]}
        receiver = json.loads((task / "email_config.json").read_text())["email"]
        inbox = json.loads((self.email_data_dir / "users_data" / receiver / "emails.json").read_text())

        # Newest email per target conference (target email ids look like email_<CONF>_<track>_<n>).
        latest = {}
        for e in inbox.values():
            parts = e["id"].split("_")
            if parts[0] == "email" and parts[1] in targets:
                latest[parts[1]] = max(latest.get(parts[1], ""), e["date"])

        today = f"{self.base_date} 00:00:00"
        deadline = {c: t["deadline"] for c, t in targets.items()}  # current deadline per conference
        rng = random.Random(f"{self.seed}-fact-revisions")
        state = random.getstate()  # the generator reseeds the global RNG
        try:
            gen = self._load_email_generator()
            used = set()
            for rev in facts:
                # Prefer conferences whose own emails are all older than today: the new email is
                # then dated before the newest emails in the inbox (buried, not on top).
                free = sorted(c for c in targets if c not in used)
                old_enough = [c for c in free if latest[c] < today]
                conf = rev.get("conference") or rng.choice(old_enough or free)
                used.add(conf)
                assert gen.CONFERENCES[conf]["full_name"] == targets[conf]["full_name"], conf

                track = targets[conf]["track"]
                old = deadline[conf]
                new = (datetime.fromisoformat(old) + timedelta(days=rev.get("shift_days", 2))).isoformat()
                deadline[conf] = new
                sent = (datetime.strptime(latest[conf], "%Y-%m-%d %H:%M:%S")
                        + timedelta(hours=rng.randint(8, 18), minutes=rng.randint(0, 59))
                        ).strftime("%Y-%m-%d %H:%M:%S")
                raw = gen.generate_camera_ready_email(conf, track, new, sent,
                                                      is_extension=True, old_deadline=old)
                eid = None
                while eid is None or eid in inbox:
                    eid = f"email_{conf}_{track}_{rng.randint(1000, 9999)}"
                rev.update(
                    conference=conf, track=track, old_deadline=old, new_deadline=new,
                    receiver=receiver, buried=sent < today,
                    email={  # same fields as preprocess/main.py import_emails_to_database
                        "id": eid, "subject": raw["subject"], "from": raw["from_addr"], "to": receiver,
                        "cc": None, "bcc": None, "date": sent,
                        "message_id": f"<{eid}@{raw['from_addr'].split('@')[1]}>",
                        "body": raw["body_text"], "html_body": raw["body_html"],
                        "is_read": False, "is_important": False, "folder": "INBOX", "attachments": [],
                    },
                )
                self.logger.info(f"fact revision {rev['id']}: {conf} {old} -> {new}, email dated {sent}")
        finally:
            random.setstate(state)
    def _resolve_exception_revisions(self) -> None:
        """Pick a conference for each "exception" revision ("leave <CONF> alone from now on")
        and fill it into the message. Never one that a fact revision changes."""
        revs = self.perturbations.get("revisions", [])
        exceptions = [r for r in revs if r.get("kind") == "exception"]
        if not exceptions:
            return
        meta = json.loads((Path(self.task_dir) / "groundtruth_workspace" / "conference_metadata.json").read_text())
        taken = {r["conference"] for r in revs if r.get("kind") == "fact"}
        rng = random.Random(f"{self.seed}-exception-revisions")
        for rev in exceptions:
            free = sorted(c["conference"] for c in meta["target_info"]["conferences"] if c["conference"] not in taken)
            conf = rev.get("conference") or rng.choice(free)
            taken.add(conf)
            rev["conference"] = conf
            rev["message"] = rev["message"].format(conference=conf)
            self.logger.info(f"exception revision {rev['id']}: {conf}")
    def on_revision_delivered(self, rev_id: str) -> None:
        """Runner hook, called when a revision's follow-up goes out.

        A "fact" revision adds its extension email to the inbox; the email server reloads
        emails.json when it changes, so the agent sees it on its next email call.
        """
        rev = next((r for r in (self.perturbations or {}).get("revisions", []) if r["id"] == rev_id), None)
        if not rev or rev.get("kind") != "fact":
            return
        if "email" not in rev:
            raise RuntimeError(f"fact revision {rev_id} was not resolved at reset(); see logs/env.log")
        user_dir = self.email_data_dir / "users_data" / rev["receiver"]
        emails = json.loads((user_dir / "emails.json").read_text())
        if rev["email"]["id"] in emails:
            return
        emails[rev["email"]["id"]] = rev["email"]
        folders = json.loads((user_dir / "folders.json").read_text())
        box = folders.setdefault("INBOX", {"total": 0, "unread": 0})
        box["total"] += 1
        box["unread"] += 1
        # folders.json first: the server reloads both files once it sees emails.json change.
        _write_json_atomic(user_dir / "folders.json", folders)
        _write_json_atomic(user_dir / "emails.json", emails)
        self.logger.info(f"revision {rev_id}: added '{rev['email']['subject']}' dated {rev['email']['date']}")

    def step(self, action: str) -> Tuple[str, float, bool, bool, Dict[str, Any]]:
        """Execute environment step and check agent's calendar reminder results.
        
        Args:
            action: Agent's action (typically triggered by claim_done tool)
        
        Returns:
            Tuple[str, float, bool, bool, Dict[str, Any]]: 
                (observation, reward, terminated, truncated, info)
        """
        super().step(action)
        
        # Import evaluation module using importlib to avoid conflicts
        try:
            import importlib.util
            env_dir = Path(__file__).parent
            evaluation_main_path = env_dir / "evaluation" / "main.py"
            
            # Load module with a unique name to avoid conflicts with other environments
            spec = importlib.util.spec_from_file_location(
                f"set_conf_cr_ddl_s2l_{id(self)}.evaluation_main",
                evaluation_main_path
            )
            evaluation_main_module = importlib.util.module_from_spec(spec)
            
            # Set environment variables before loading
            import os
            os.environ['CALENDAR_DATA_DIR'] = str(self.calendar_data_dir)
            
            # Set up sys.path before loading
            sys.path.insert(0, str(env_dir / "evaluation"))
            try:
                spec.loader.exec_module(evaluation_main_module)
            finally:
                # Remove from sys.path after loading
                if str(env_dir / "evaluation") in sys.path:
                    sys.path.remove(str(env_dir / "evaluation"))
            
        except ImportError as e:
            error_msg = f"Failed to import evaluation module: {e}"
            self.logger.error(error_msg)
            return TERMINAL_STATE, 0.0, True, True, {"error": error_msg}
        
        self.logger.info("\n" + "=" * 80)
        self.logger.info("Starting task evaluation")
        self.logger.info("=" * 80)
        
        # Execute evaluation
        try:
            # Import CalendarDatabase
            current_dir = Path(__file__).parent
            sys.path.insert(0, str(current_dir))

            from mcp_convert.mcps.calendar.database_utils import CalendarDatabase
            
            # Initialize Calendar database
            self.logger.info("\nInitializing Calendar Database for evaluation...")
            calendar_db_dir = str(self.calendar_data_dir)
            self.logger.info(f"Using Calendar Database Directory: {calendar_db_dir}")
            
            if not Path(calendar_db_dir).exists():
                error_msg = f"Calendar database directory not found: {calendar_db_dir}"
                self.logger.error(error_msg)
                return TERMINAL_STATE, 0.0, True, True, {"error": error_msg}
            
            calendar_db = CalendarDatabase(data_dir=calendar_db_dir)
            
            # Define paths
            groundtruth_workspace = Path(self.task_dir) / "groundtruth_workspace"
            
            self.logger.info("\nValidating calendar reminders...")
            
            # Validate groundtruth workspace existence
            if not groundtruth_workspace.exists():
                error_msg = f"Missing groundtruth workspace: {groundtruth_workspace}"
                self.logger.error(error_msg)
                return TERMINAL_STATE, 0.0, True, True, {"error": error_msg}
            
            # Run evaluation via subprocess to avoid module conflicts
            try:
                import subprocess

                # Use original evaluation script (no need to copy)
                eval_main = env_dir / "evaluation" / "main.py"

                # Set up environment
                env = os.environ.copy()
                env['CALENDAR_DATA_DIR'] = str(self.calendar_data_dir)

                cmd = [
                    sys.executable,
                    str(eval_main),
                    "--agent_workspace", str(self.agent_workspace),
                    "--groundtruth_workspace", str(groundtruth_workspace),
                    "--task-root", str(self.task_dir)  # Pass task directory
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=str(self.task_dir),  # Use task directory as working directory
                    env=env
                )

                if result.stdout:
                    self.logger.info(result.stdout)

                # Check if evaluation succeeded
                evaluation_passed = (result.returncode == 0)
                
                if evaluation_passed:
                    observation = self._create_success_observation()
                    reward = 1.0
                    info = {
                        "success": True,
                        "error": None,
                        "evaluation": "passed"
                    }
                else:
                    error_msg = "Calendar reminder validation failed. Check the evaluation output above."
                    if result.stderr:
                        error_msg += f"\n{result.stderr}"
                    observation = self._create_failure_observation(error_msg)
                    reward = 0.0
                    info = {
                        "success": False,
                        "error": error_msg,
                        "evaluation": "failed"
                    }
                
            except Exception as e:
                error_msg = f"Evaluation subprocess error: {str(e)}"
                self.logger.error(error_msg)
                self.logger.error(traceback.format_exc())
                
                observation = self._create_failure_observation(error_msg)
                reward = 0.0
                info = {
                    "success": False,
                    "error": error_msg,
                    "evaluation": "failed"
                }
                
        except Exception as e:
            error_msg = f"Evaluation error: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(traceback.format_exc())
            
            observation = self._create_failure_observation(error_msg)
            reward = 0.0
            info = {
                "success": False,
                "error": error_msg,
                "evaluation": "failed"
            }
        
        # Terminate environment
        terminated = True
        truncated = False
        
        return observation, reward, terminated, truncated, info
    
    def _create_success_observation(self) -> str:
        """Create success observation message.
        
        Returns:
            str: Formatted success message
        """
        return (
            "\n" + "=" * 80 + "\n"
            "Task Evaluation Result: Success!\n"
            "=" * 80 + "\n"
            "All checks passed:\n"
            "  ✓ All target conferences identified from emails\n"
            "  ✓ Calendar reminders set for all camera-ready deadlines\n"
            "  ✓ Reminder times are exactly 3 hours before deadlines\n"
            "  ✓ Event summaries contain correct keywords (conference name, camera, ready)\n"
            "  ✓ All reminders created with correct date and time\n"
            "\nCongratulations! You have successfully completed the conference reminder task.\n"
            "=" * 80 + "\n"
        )
    
    def _create_failure_observation(self, error: str) -> str:
        """Create failure observation message.
        
        Args:
            error: Error message describing what failed
        
        Returns:
            str: Formatted failure message
        """
        return (
            "\n" + "=" * 80 + "\n"
            "Task Evaluation Result: Failed\n"
            "=" * 80 + "\n"
            f"Error details:\n{error}\n"
            "\nPlease review and fix the issues above.\n"
            "Hints:\n"
            "  - Did you check all emails for camera-ready deadline notifications?\n"
            "  - Did you identify all target conferences (not just noise emails)?\n"
            "  - Did you set calendar reminders 3 hours before each deadline?\n"
            "  - Did you include relevant keywords in event summaries?\n"
            "  - Did you handle deadline extensions correctly (use the latest deadline)?\n"
            "  - Did you verify the reminder times match the deadline - 3 hours?\n"
            "=" * 80 + "\n"
        )
    
    def _create_error_observation(self, error_msg: str) -> str:
        """Create error observation message for evaluation errors.
        
        Args:
            error_msg: Error message describing the evaluation error
        
        Returns:
            str: Formatted error message
        """
        return (
            "\n" + "=" * 80 + "\n"
            "Task Evaluation Error\n"
            "=" * 80 + "\n"
            f"Error details:\n{error_msg}\n"
            "=" * 80 + "\n"
        )



