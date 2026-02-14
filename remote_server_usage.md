# LOCA-bench Remote Sandbox Server Usage

## Overview

The LOCA-bench remote server exposes a FastAPI-based HTTP API (`gem/server/http_server.py`) that manages environment sessions, MCP tool servers, and task evaluation. It can run either as a **local Python process** or inside a **Docker/Podman container** (sandbox mode). The client (`gem/client/remote_env_client.py`) communicates with it over HTTP.

## 1. Launching the HTTP Server

### Option A: Local Process (Development/Debugging)

Start the server directly with Python:

```bash
export PYTHONPATH="/path/to/LOCA-bench-lite:/path/to/LOCA-bench-lite/mcp-convert"

python -u gem/server/http_server.py \
  --host 0.0.0.0 \
  --port 9000 \
  --workspace-base ./outputs \
  --log-level DEBUG
```

**Parameters:**

| Parameter          | Default              | Description                              |
|--------------------|----------------------|------------------------------------------|
| `--host`           | `0.0.0.0`            | Host to bind to                          |
| `--port`           | `8000`               | Port to bind to                          |
| `--workspace-base` | `/workspace/outputs`  | Base directory for task workspaces        |
| `--log-level`      | `INFO`               | Logging level (`DEBUG`, `INFO`, `WARNING`)|

### Option B: Docker Container (Sandbox/Production)

**Build the image:**

```bash
docker build -t loca-bench:latest .
```

**Run the container:**

```bash
docker run --rm \
  --name loca-task-my-task-0 \
  -p 9000:8000 \
  -v /path/to/task_workspace_parent:/workspace/outputs/tasks/TaskName \
  loca-bench:latest
```

The container's default `CMD` is:

```
python gem/server/http_server.py --host 0.0.0.0 --port 8000
```

The container exposes port `8000` internally; map it to any host port with `-p <host_port>:8000`.

### Option C: Via `run_remote.sh` (Automated)

The shell wrapper handles server lifecycle automatically:

```bash
cd inference

# Local mode
./run_remote.sh --execution-mode local \
  --config-file react/debug_woocom.json \
  --model deepseek-reasoner \
  --base-port 9000

# Sandbox mode (Docker)
./run_remote.sh --execution-mode sandbox \
  --config-file react/debug_woocom.json \
  --model deepseek-reasoner \
  --base-port 9000
```

In both modes, the script automatically:
1. Finds an available port starting from `base_port + task_id`
2. Starts the server (local subprocess or Docker container)
3. Waits for health check to pass
4. Runs the inference client
5. Cleans up the server on completion

---

## 2. Health Check

**Endpoint:** `GET /api/v1/health`

**Request:**

```bash
curl http://localhost:9000/api/v1/health
```

**Response (200 OK):**

```json
{
  "status": "ok",
  "active_sessions": 0
}
```

**Programmatic polling (Python client):**

```python
from gem.client.remote_env_client import RemoteEnvironmentClient

client = RemoteEnvironmentClient(
    server_url="http://localhost:9000",
    config=config,
    task_workspace="/path/to/task_workspace",
    agent_workspace="/path/to/agent_workspace"
)

# Polls GET /api/v1/health up to 30 times at 1s intervals
is_ready = client.wait_for_server(max_retries=30, retry_interval=1.0)
```

---

## 3. Initialize an Environment

**Endpoint:** `POST /api/v1/init`

This creates an `EnvironmentSession` which:
1. Dynamically imports and instantiates the environment class
2. Launches all configured MCP servers (stdio-based subprocesses)
3. Wraps the environment with OpenAI-compatible tool calling
4. Calls `env.reset(seed)` to populate mock databases and generate the task prompt
5. Returns a session ID, the initial observation (task instructions), and all available tool schemas

**Request:**

```bash
curl -X POST http://localhost:9000/api/v1/init \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "WoocommerceNewWelcome-easy",
    "config": {
      "name": "WoocommerceNewWelcome-easy",
      "env_class": "gem.envs.woocommerce_new_welcome_s2l.woocommerce_new_welcome_s2l.WoocommerceNewWelcomeS2LEnv",
      "env_params": {
        "total_orders": 25,
        "first_time_customers": 5,
        "noise_outside_window": 2,
        "noise_incomplete": 2,
        "seed": 42,
        "verbose": false
      },
      "mcp_servers": {
        "woocommerce": {
          "enabled": true,
          "type": "woocommerce",
          "params": {
            "data_dir": "{task_workspace}/local_db/woocommerce"
          }
        },
        "google_cloud": {
          "enabled": true,
          "type": "google_cloud",
          "params": {
            "data_dir": "{task_workspace}/local_db/google_cloud"
          }
        },
        "email": {
          "enabled": true,
          "type": "email",
          "params": {
            "data_dir": "{task_workspace}/local_db/emails",
            "email": "admin@woocommerce.local",
            "password": "admin123"
          }
        },
        "filesystem": {
          "enabled": true,
          "type": "filesystem",
          "params": {
            "workspace_path": "{agent_workspace}"
          }
        },
        "python_execute": {
          "enabled": true,
          "type": "python_execute",
          "params": {
            "workspace_dir": "{agent_workspace}"
          }
        },
        "claim_done": {
          "enabled": true,
          "type": "claim_done",
          "params": {}
        }
      }
    },
    "task_workspace": "/workspace/outputs/tasks/WoocommerceNewWelcome/run_0",
    "agent_workspace": "/workspace/outputs/tasks/WoocommerceNewWelcome/run_0/agent"
  }'
```

**Response (200 OK):**

```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "observation": "You are an e-commerce operations assistant...",
  "info": {},
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "wc_get_orders",
        "description": "Get WooCommerce orders...",
        "parameters": { "..." : "..." }
      }
    }
  ]
}
```

**Key notes:**
- `{task_workspace}` and `{agent_workspace}` placeholders in MCP server params are replaced with actual paths at runtime.
- The `tools` array contains OpenAI-format tool schemas that can be passed directly to an LLM's `tools` parameter.
- The `session_id` is required for all subsequent requests.

---

## 4. Execute a Tool

**Endpoint:** `POST /api/v1/execute_tool`

Executes a single tool call within a session. The server routes the call through the MCP server infrastructure.

**Request:**

```bash
curl -X POST http://localhost:9000/api/v1/execute_tool \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "tool_name": "wc_get_orders",
    "arguments": {
      "status": "completed",
      "per_page": 10
    },
    "tool_call_id": "call_abc123"
  }'
```

**Response (200 OK):**

```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "[{\"id\": 1, \"status\": \"completed\"}]",
  "success": true,
  "error": null
}
```

**Error case (tool not found or execution failure):**

```json
{
  "role": "tool",
  "tool_call_id": "call_abc123",
  "content": "Error executing tool: ...",
  "success": false,
  "error": "Tool not found: invalid_tool_name"
}
```

**Notes:**
- The `content` field contains the raw string result from the MCP server (typically JSON-serialized).
- The `role` is always `"tool"`, matching the OpenAI chat completion message format.
- The response can be appended directly to an LLM conversation as a tool result message.
- Request timeout is 120 seconds on the client side.

---

## 5. Evaluate Task Completion

**Endpoint:** `POST /api/v1/evaluate`

Triggers evaluation of the agent's work by calling the environment's `step("claim_done")`.

**Request:**

```bash
curl -X POST http://localhost:9000/api/v1/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "action": "claim_done"
  }'
```

**Response (200 OK):**

```json
{
  "observation": "Evaluation complete.",
  "reward": 0.85,
  "terminated": true,
  "truncated": false,
  "info": {
    "score_breakdown": {}
  }
}
```

**Notes:**
- Before evaluation, the server closes all MCP database connections to avoid read conflicts.
- `reward` is a float between 0.0 and 1.0 indicating task completion score.

---

## 6. Cleanup a Session

**Endpoint:** `POST /api/v1/cleanup`

Stops MCP servers and releases session resources.

**Request:**

```bash
curl -X POST http://localhost:9000/api/v1/cleanup \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }'
```

**Response (200 OK):**

```json
{
  "success": true
}
```

---

## 7. Typical Workflow (End-to-End)

```
1. Start server          (launch process or container)
2. Health check          GET  /api/v1/health        → wait until {"status": "ok"}
3. Initialize env        POST /api/v1/init           → get session_id + tools + observation
4. Agent loop:
   a. Send observation + tools to LLM
   b. LLM returns tool_calls
   c. For each tool_call:
      Execute tool      POST /api/v1/execute_tool   → get tool result
   d. Append tool results to conversation
   e. Repeat until LLM calls "claim_done"
5. Evaluate              POST /api/v1/evaluate       → get reward
6. Cleanup               POST /api/v1/cleanup        → release resources
7. Stop server           (terminate process or container)
```

---

## 8. Python Client Example

```python
from gem.client.remote_env_client import RemoteEnvironmentClient

config = { ... }  # loaded from JSON config file

with RemoteEnvironmentClient(
    server_url="http://localhost:9000",
    config=config,
    task_workspace="/path/to/task_workspace",
    agent_workspace="/path/to/agent_workspace",
    timeout=300
) as client:
    # Wait for server
    client.wait_for_server()

    # Initialize environment
    observation, info = client.reset()
    tools = client.get_tools()  # OpenAI-format tool schemas

    # Execute a tool
    result = client.execute_tool(
        tool_name="wc_get_orders",
        arguments={"status": "completed"},
        tool_call_id="call_001"
    )
    print(result["content"])   # tool output string
    print(result["success"])   # True/False

    # Execute multiple tools (from LLM response)
    tool_calls = [
        {
            "id": "call_002",
            "type": "function",
            "function": {
                "name": "bq_query",
                "arguments": "{\"query\": \"SELECT * FROM table LIMIT 10\"}"
            }
        }
    ]
    results = client.execute_tools(tool_calls)

    # Evaluate
    obs, reward, terminated, truncated, info = client.evaluate()

    # Cleanup is automatic via context manager
```

---

## 9. API Reference Summary

| Method | Endpoint               | Request Body                                          | Response                                             |
|--------|------------------------|-------------------------------------------------------|------------------------------------------------------|
| GET    | `/api/v1/health`       | —                                                     | `{status, active_sessions}`                          |
| POST   | `/api/v1/init`         | `{task_name, config, task_workspace, agent_workspace}` | `{session_id, observation, info, tools}`             |
| POST   | `/api/v1/execute_tool` | `{session_id, tool_name, arguments, tool_call_id}`    | `{role, tool_call_id, content, success, error}`      |
| POST   | `/api/v1/evaluate`     | `{session_id, action}`                                | `{observation, reward, terminated, truncated, info}` |
| POST   | `/api/v1/cleanup`      | `{session_id}`                                        | `{success}`                                          |
