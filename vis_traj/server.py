#!/usr/bin/env python3
"""
Trajectory Visualization Server for LOCA-bench.

Serves trajectory data from LOCA-bench evaluation outputs and provides
a web UI for interactive trajectory replay.

Usage:
    python vis_traj/server.py --res_path /path/to/eval/output --port 8000
"""

import argparse
import json
import os
import sys
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote

TRAJECTORY_CACHE = {}
CONFIG_DATA = None
FILE_LIST = []


def load_trajectories(res_path: str):
    """Recursively scan tasks/config_X/run_Y/trajectory.json and cache them."""
    global TRAJECTORY_CACHE, CONFIG_DATA, FILE_LIST

    tasks_dir = os.path.join(res_path, "tasks")
    if not os.path.isdir(tasks_dir):
        print(f"Warning: tasks directory not found at {tasks_dir}")
        return

    # Load config for task names
    config_names = {}
    for config_file in ["config_react.json", "config_ptc.json", "config_memory_tool.json"]:
        config_path = os.path.join(res_path, config_file)
        if os.path.isfile(config_path):
            try:
                with open(config_path, "r") as f:
                    CONFIG_DATA = json.load(f)
                configs = CONFIG_DATA.get("configurations", [])
                for i, cfg in enumerate(configs):
                    config_names[i] = cfg.get("name", f"config_{i}")
                print(f"Loaded {len(configs)} configurations from {config_file}")
            except Exception as e:
                print(f"Warning: failed to load {config_file}: {e}")
            break

    # Scan trajectory files
    config_dirs = sorted(
        [d for d in os.listdir(tasks_dir) if d.startswith("config_")],
        key=lambda x: int(x.split("_")[1]),
    )

    for config_dir in config_dirs:
        config_idx = int(config_dir.split("_")[1])
        config_path = os.path.join(tasks_dir, config_dir)
        if not os.path.isdir(config_path):
            continue

        run_dirs = sorted(
            [d for d in os.listdir(config_path) if d.startswith("run_")],
            key=lambda x: int(x.split("_")[1]),
        )

        for run_dir in run_dirs:
            run_idx = int(run_dir.split("_")[1])
            traj_path = os.path.join(config_path, run_dir, "trajectory.json")
            if not os.path.isfile(traj_path):
                continue

            try:
                with open(traj_path, "r") as f:
                    traj_data = json.load(f)

                cache_key = f"{config_dir}/{run_dir}"
                TRAJECTORY_CACHE[cache_key] = traj_data

                task_name = config_names.get(config_idx, config_dir)
                metrics = traj_data.get("metrics", {})

                FILE_LIST.append(
                    {
                        "key": cache_key,
                        "config_idx": config_idx,
                        "run_idx": run_idx,
                        "config_dir": config_dir,
                        "run_dir": run_dir,
                        "task_name": task_name,
                        "accuracy": metrics.get("accuracy", None),
                        "total_steps": metrics.get("total_steps", None),
                        "completed": metrics.get("completed", None),
                    }
                )
            except Exception as e:
                print(f"Warning: failed to load {traj_path}: {e}")

    print(f"Loaded {len(TRAJECTORY_CACHE)} trajectories")


class TrajectoryHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for trajectory visualization."""

    def __init__(self, *args, static_dir=None, **kwargs):
        self.static_dir = static_dir
        super().__init__(*args, directory=static_dir, **kwargs)

    def do_GET(self):
        path = unquote(self.path)

        if path == "/api/files":
            self.send_json_response(FILE_LIST)
        elif path.startswith("/api/trajectory/"):
            key = path[len("/api/trajectory/"):]
            if key in TRAJECTORY_CACHE:
                self.send_json_response(TRAJECTORY_CACHE[key])
            else:
                self.send_error_response(404, f"Trajectory not found: {key}")
        elif path == "/api/config":
            if CONFIG_DATA is not None:
                self.send_json_response(CONFIG_DATA)
            else:
                self.send_error_response(404, "No config data loaded")
        else:
            # Serve static files
            super().do_GET()

    def send_json_response(self, data):
        response = json.dumps(data)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response.encode("utf-8"))))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(response.encode("utf-8"))

    def send_error_response(self, code, message):
        response = json.dumps({"error": message})
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(response.encode("utf-8"))

    def log_message(self, format, *args):
        # Suppress request logging for cleaner output
        pass


def main():
    # Ensure unbuffered output
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(description="LOCA Trajectory Visualization Server")
    parser.add_argument(
        "--res_path",
        type=str,
        required=True,
        help="Path to evaluation output directory (containing tasks/ and config_*.json)",
    )
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    args = parser.parse_args()

    res_path = os.path.abspath(args.res_path)
    if not os.path.isdir(res_path):
        print(f"Error: {res_path} is not a directory")
        return

    print(f"Loading trajectories from: {res_path}")
    load_trajectories(res_path)

    if not TRAJECTORY_CACHE:
        print("Warning: no trajectories found")

    static_dir = os.path.dirname(os.path.abspath(__file__))
    handler = partial(TrajectoryHandler, static_dir=static_dir)

    server = HTTPServer(("", args.port), handler)
    print(f"Server running at http://localhost:{args.port}")
    print(f"Serving {len(TRAJECTORY_CACHE)} trajectories")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()


if __name__ == "__main__":
    main()
