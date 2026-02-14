<div align="center">

# LOCA-bench: Benchmarking Language Agents Under Controllable and Extreme Context Growth

[![Paper](https://img.shields.io/badge/Paper-arXiv-red)](https://arxiv.org/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

</div>

> **Note:** This branch is designed for facilitating large-scale evaluation deployment on production-level frameworks. You can easily incorporate it into any other framework based on this repo. Due to this goal, we only guarantee the calibration of the **ReAct** scaffolding strategy — all other context management methods (PTC, Memory Tool, etc.) are **not** calibrated in this branch. For fully calibrated results across all strategies, please refer to the [main branch](https://github.com/hkust-nlp/LOCA-bench/).

## Overview

**LOCA-bench** (LOng-Context Agents benchmark) is designed to evaluate language agents under extreme and controllable context growth scenarios. Given a task prompt, LOCA-bench leverages automated and scalable control of environment states to regulate the agent's context length.

### Key Highlights

- **Controllable Context Growth**: Extend context length to arbitrary sizes while keeping task semantics fixed
- **Comprehensive Evaluation**: Evaluate language agents as a combination of models and scaffolds
- **Multiple Strategies**: Support various context management strategies for comparison

<div align="center">
<img src="assets/fig1-v2.3.5.png" width="800" alt="LOCA-bench Overview">
</div>

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Remote Server API](#remote-server-api)
- [Context Management Strategies](#context-management-strategies)
- [Configuration](#configuration)
- [Evaluation](#evaluation)
- [Features](#features)
  - [Mock MCP Servers](#mock-mcp-servers)
  - [Adjustable Environment](#adjustable-environment)
  - [Environment Description Length](#environment-description-length)
  - [Context Engineering Strategies](#context-engineering-strategies)
- [Citation](#citation)
- [License](#license)

---

## Installation

Our implementation is based on [GEM](https://github.com/axon-rl/gem). Follow the steps below to set up the environment:

### Local Installation

```bash
# Create and activate conda environment
conda create -n loca-bench python=3.10.0
conda activate loca-bench

# Clone the repository
git clone https://github.com/hkust-nlp/LOCA-bench.git
cd LOCA-bench

# Install dependencies
bash install.sh
```

### Docker Installation (for Sandbox Mode)

If you plan to use sandbox mode for isolated execution, build the Docker image:

```bash
# Build the Docker image
docker build -t loca-bench:latest .

# Verify the build
docker run --rm loca-bench:latest python --version
```

Alternatively, use Podman:

```bash
# Build with Podman
podman build -t loca-bench:latest .

# Use with --container-runtime podman
./run_remote.sh --execution-mode sandbox --container-runtime podman ...
```

---

## Quick Start

### 1. Set Up API Credentials

Configure your API key and base URL via command line or environment variables:

| Provider | Base URL |
|----------|----------|
| DeepSeek | `https://api.deepseek.com/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| AIHubMix | `https://aihubmix.com/v1` |

### 2. Run Inference

LOCA-bench uses a client-server architecture that separates LLM API calls (client) from tool execution (server). Navigate to the inference directory and choose an execution mode:

**Local Mode** (Recommended for development/debugging):
```bash
cd inference
./run_remote.sh \
  --execution-mode local \
  --config-file final_8k_set_config_multi_seed.json \
  --model deepseek-reasoner \
  --max-context-size 130000 \
  --api-key $YOUR_API_KEY \
  --base-url https://api.deepseek.com/v1
```

**Sandbox Mode** (Recommended for production/isolation):
```bash
cd inference
./run_remote.sh \
  --execution-mode sandbox \
  --config-file final_8k_set_config_multi_seed.json \
  --model deepseek-reasoner \
  --max-context-size 130000 \
  --api-key $YOUR_API_KEY \
  --base-url https://api.deepseek.com/v1
```

### Execution Modes

| Mode | Description | Docker Required | Use Case |
|------|-------------|-----------------|----------|
| `local` | Server runs as local Python process | No | Development, debugging |
| `sandbox` | Server runs in Docker/Podman container | Yes | Production, isolation |

Both modes produce identical results. See [Remote Server Usage](remote_server_usage.md) for the full HTTP API reference.

Environment configurations are provided under `inference/react/` with preset environment description lengths: **8K, 16K, 32K, 64K, 96K, 128K, and 256K** tokens.

---

## Architecture

LOCA-bench uses a **client-server architecture** that separates concerns for better debugging, isolation, and scalability:

```
┌─────────────────────────────┐     HTTP      ┌─────────────────────────────┐
│         Client              │ ◄──────────► │         Server              │
│  (inference/run_react_      │               │  (gem/server/http_server.py)│
│   remote.py)                │               │                             │
├─────────────────────────────┤               ├─────────────────────────────┤
│ • Load configurations       │               │ • Environment management    │
│ • LLM API calls             │               │ • MCP server lifecycle      │
│ • Message history           │               │ • Tool execution            │
│ • Context management        │               │ • Evaluation                │
│ • Result saving             │               │ • Database operations       │
└─────────────────────────────┘               └─────────────────────────────┘
```

### Key Components

| Component | Location | Description |
|-----------|----------|-------------|
| Client | `inference/run_react_remote.py` | Orchestrates inference, calls LLM APIs, manages context |
| Server | `gem/server/http_server.py` | Runs environments, executes tools via HTTP endpoints |
| Remote Client | `gem/client/remote_env_client.py` | HTTP client for communicating with server |
| MCP Servers | `mcp_convert/mcps/` | Mock service backends (BigQuery, Canvas, etc.) |


---

## Remote Server API

The server (`gem/server/http_server.py`) exposes a FastAPI-based HTTP API for environment management and tool execution. Full details are in [remote_server_usage.md](remote_server_usage.md).

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check and active session count |
| POST | `/api/v1/init` | Initialize environment, launch MCP servers, return tools |
| POST | `/api/v1/execute_tool` | Execute a tool call within a session |
| POST | `/api/v1/evaluate` | Evaluate task completion and get reward |
| POST | `/api/v1/cleanup` | Release session resources |

---

## Context Management Strategies


LOCA-bench supports multiple context management strategies:

| Strategy | Description | Config Location |
|----------|-------------|-----------------|
| `react` (default) | Basic reactive agent framework | `inference/react/` |
| `ptc` | Programmatic Tool Calling - orchestrate tools via code execution | `inference/ptc/` |
| `memory_tool` | Persistent storage and retrieval across conversations | `inference/memory_tool/` |


### Usage Examples

**Basic ReAct Run (Local Mode):**

```bash
./run_remote.sh --execution-mode local --config-file final_8k_set_config_multi_seed.json
```

---

## Configuration

### Common Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--config-file` | Configuration JSON filename | *Required* |
| `--strategy` | Context strategy: `react`, `ptc`, `memory_tool` | `react` |
| `--model` | Model name | `deepseek-reasoner` |
| `--base-url` | API base URL | - |
| `--api-key` | API key for the LLM provider | - |
| `--max-workers` | Number of parallel workers | `20` |
| `--runs-per-config` | Number of runs per configuration | `1` |
| `--max-tokens` | Maximum tokens for generation | `32768` |
| `--max-context-size` | Maximum context window size | `128000` |

### Remote Execution Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--execution-mode` | Execution mode: `local` or `sandbox` | `sandbox` |
| `--container-runtime` | Container runtime: `docker` or `podman` | `docker` |
| `--docker-image` | Container image for sandbox mode | `loca-bench:latest` |
| `--base-port` | Base port for servers (each task uses base-port + task_id) | `9000` |

---

## Evaluation

### Output Locations

Results are saved to:
```
PROJECT_ROOT/outputs/inf_{strategy}_{config}_{model}_{mode}_{timestamp}/
├── {TaskName}/
│   └── run_{N}/
│       ├── logs/
│       │   ├── server.log      # MCP and execution logs
│       │   └── env.log         # Environment and evaluation logs
│       ├── local_db/           # Mock databases
│       ├── agent_workspace/    # Agent working files
│       └── {task}_runN-episode.json  # Full trajectory
```

### Running Analysis

Use the analysis script to compute statistics:

```bash
cd inference
./ana.sh PROJECT_ROOT/outputs/inf_{strategy}_{config}_{model}_{mode}_{timestamp}/
```

---

## Features

### Mock MCP Servers

LOCA-bench uses local, database-backed mock servers to simulate remote service backends. This approach avoids challenges associated with real online services (authentication, concurrency limits, API changes).

**Location:** [`mcp_convert/`](mcp_convert/)

**Supported Services:**
- Google Calendar
- Canvas LMS
- Email
- BigQuery
- Google Sheets
- Snowflake
- WooCommerce

**Key Properties:**
- Identical tool interfaces to original services
- Request schema and return formats match real APIs
- No authentication required
- Transparent and controllable backend for data injection and environment manipulation

---

### Adjustable Environment

**Location:** [`gem/envs/`](gem/envs/)

Each task uses hand-written templates representing possible environment states, combined with custom generators that assemble these templates into concrete states based on configuration.

**Example:** A task requiring an agent to compile exam information from Canvas and Emails can:
- Instantiate any number of courses and exams
- Control how information is distributed between sources
- Introduce exceptions (exempt courses, courses without exams)
- Add distracting content

By adjusting configuration parameters, environment states with varying scale, difficulty, and distraction levels are automatically generated.

---

### Environment Description Length

Environment complexity is quantified by the number of tokens required to encode the environment's information.

**Measurement Process:**
1. Run scripted tool calls
2. Collect and concatenate all tool outputs an agent would need to read
3. Tokenize the aggregated text using GPT-4's tokenizer

**Preset Configurations:** [`inference/react/`](inference/react/)

| Configuration File | Environment Description Length |
|--------------------|-------------------------------|
| `final_8k_set_config_multi_seed.json` | 8K tokens |
| `final_16k_set_config_multi_seed.json` | 16K tokens |
| `final_32k_set_config_multi_seed.json` | 32K tokens |
| `final_64k_set_config_multi_seed.json` | 64K tokens |
| `final_96k_set_config_multi_seed.json` | 96K tokens |
| `final_128k_set_config_multi_seed.json` | 128K tokens |

---


## Acknowledgement
We appreciate [gem](https://github.com/axon-rl/gem) to open-source a nice agentic LLM framework, based on which we build LOCA-bench.

---

## Citation

If you find LOCA-bench useful in your research, please cite our paper:

```bibtex
@article{loca-bench2026,
  title   = {LOCA-bench: Benchmarking Language Agents Under Controllable and Extreme Context Growth},
  author  = {Zeng, Weihao and Huang, Yuzhen and He, Junxian},
  journal = {arXiv preprint arXiv:2602.07962},
  year    = {2026}
}
```




