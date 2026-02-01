# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This project is a **benchmarking suite for evaluating models and context management strategies on long-run agentic tasks**. It builds on the GEM (General Experience Maker) environment framework to test how well models handle extended multi-turn interactions with tool use, context windows, and memory management.

**Key Purpose**: Test model performance on long-context agentic tasks (8k-256k+ tokens) with various context management strategies (reset, summary, awareness, etc.).

**Project Status**: Finished and ready for refactoring for official release.

## Installation

Install from PyPI:
```bash
pip install -U gem-llm
```

Install from source (editable mode):
```bash
pip install -e .
```

Install with optional dependencies:
```bash
# For search tool support
pip install -U 'gem-llm[search]'
conda install -c pytorch -c nvidia faiss-gpu=1.8.0

# For MCP tool support
pip install -U 'gem-llm[mcp]'
```

## Common Development Commands

### Running Benchmarks (Primary Use Case)

The core benchmarking workflow uses configuration files and parallel execution:

```bash
# Basic benchmark run
cd inference
./run_parallel_test.sh config_file.json runs_per_config max_workers

# Example: Run with context management strategies
./run_parallel_test.sh final_128k_set_config.json 1 5 v2 \
  True False False 200000 0.5 True 200000 32768 0.5

# Parameters explained:
# - config_file: JSON config (env_class, env_params, mcp_servers)
# - runs_per_config: Number of runs per configuration
# - max_workers: Parallel worker count
# - v2: Configuration system version (v2 = flexible, v1 = legacy)
# - Context management params:
#   - context_reset (True/False)
#   - context_summary (True/False)
#   - context_awareness (True/False)
#   - reset_size (tokens)
#   - reset_ratio (0.0-1.0)
#   - group_by_seed (True/False)
#   - max_context_size (tokens)
#   - max_tokens (generation limit)
#   - memory_warning_threshold (0.0-1.0)
```

The script launches `run_multi_openai_v2.py` which:
1. Reads configuration JSON files defining environments and MCP servers
2. Creates isolated workspaces for each task
3. Executes parallel inference with specified models
4. Saves results to `evals/benchmarks/`

### Analyzing Results

```bash
# Analyze benchmark outputs
cd inference
python ana_all_configs.py

# View summary
cat evals/benchmarks/inf_*/summary-*.json | python -m json.tool
```

### Testing
```bash
# Run all tests
make test
# Or directly:
pytest -s
```

### Code Quality
```bash
# Format code (autoflake, black, isort)
make format

# Lint code (isort, pylint)
make lint

# Check docstring style
make check-docstyle

# Run all checks
make checks
```

### Building and Publishing
```bash
# Build package
make package

# Publish to PyPI
make publish

# Clean build artifacts
make clean
```

## Architecture

### Benchmarking Pipeline

The benchmarking system has three main layers:

1. **Configuration Layer** (`inference/*.json`):
   - JSON files define test scenarios with `configurations` list
   - Each configuration specifies:
     - `env_class`: Full path to environment class (e.g., `gem.envs.ab_testing_s2l.ab_testing_s2l.ABTestingS2LEnv`)
     - `env_params`: Environment initialization parameters (num_scenarios, seed, etc.)
     - `mcp_servers`: Dictionary of MCP tool servers to enable (google_cloud, python_execute, filesystem, claim_done, etc.)

2. **Execution Layer** (`inference/run_multi_openai_v2.py`):
   - Parallel execution of multiple configurations
   - Context management strategies (reset, summary, awareness)
   - Model API integration (OpenAI, Anthropic, custom endpoints)
   - Workspace isolation per task instance
   - Episode tracking and logging

3. **Environment Layer** (`gem/envs/` and `gem/tools/mcp_server/`):
   - Task environments (s2l = structured-to-long tasks)
   - Mock MCP servers for tool execution
   - Standardized observation/action interface

### Core API Structure

The codebase follows the OpenAI Gym pattern with these key components:

1. **`gem/core.py`**: Defines the base `Env` and `EnvWrapper` abstract classes
   - `Env.step(action)` → returns (observation, reward, terminated, truncated, info)
   - `Env.reset(seed)` → returns (observation, info)
   - `Env.spawn(same_state)` → creates new env instances with same config

2. **`gem/envs/registration.py`**: Environment registry system
   - `register(env_id, entry_point, **kwargs)` - register new environments
   - `make(env_id, **kwargs)` - create single environment instances
   - `make_vec(env_ids, wrappers, vec_kwargs, async_mode, root_dir)` - create vectorized environments
   - Supports both sync and async vectorization for parallel execution

3. **Environment Categories** (`gem/envs/`):

   **Primary Focus - Long-Run Task Environments (s2l)**:
   - `ab_testing_s2l` - A/B testing analysis with Google Cloud
   - `academic_warning_s2l` - Academic warning system management
   - `apply_phd_email_s2l` - PhD application email handling
   - `canvas_arrange_exam_s2l` - Canvas LMS exam scheduling
   - `canvas_list_test_s2l` - Canvas quiz management
   - `course_assistant_s2l` - Course assistant tasks
   - `excel_market_research_s2l` - Market research in Excel
   - `filter_low_selling_products_s2l` - Product filtering
   - `machine_operating_s2l` - Machine operation tasks
   - `nhl_b2b_analysis_s2l` - NHL back-to-back analysis
   - `payable_invoice_checker_s2l` - Invoice checking
   - `set_conf_cr_ddl_s2l` - Conference deadline setting
   - `update_material_inventory_s2l` - Inventory management
   - `woocommerce_new_welcome_s2l` - WooCommerce welcome messages
   - `woocommerce_stock_alert_s2l` - WooCommerce stock alerts

   **General Environments** (inherited from base GEM):
   - **Games**: `game:GuessTheNumber-v0`, `game:Sudoku-v0-easy`
   - **Math**: `math:GSM8K`, `math:Math12K`, `math:DeepScaleR40K`
   - **Code**: `code:CodeContest`, `code:Taco8k`
   - **QA**: `qa:NaturalQuestions`, `qa:HotpotQA`
   - **ReasoningGym**: `rg:arc_1d`, `rg:letter_counting`

### MCP Server System (Core to Benchmarking)

The benchmarking suite uses **mock MCP (Model Context Protocol) servers** to provide tool capabilities to agents. These are located in `gem/tools/mcp_server/` and simulate real-world tool environments.

**Available MCP Servers**:
- `canvas` - Canvas LMS API (courses, quizzes, submissions)
- `email` - Email client (IMAP/SMTP operations)
- `excel` - Excel file manipulation
- `google_cloud` - Google Cloud Storage operations
- `google_sheet` - Google Sheets API
- `python_execute` - Python code execution in isolated workspace
- `filesystem` - File system operations (read, write, list)
- `terminal` - Terminal command execution
- `claim_done` - Task completion signaling
- `memory` / `memory_tool` - Persistent memory storage
- `programmatic_tool_calling` - Structured tool calling interface
- `pdf_tools` - PDF manipulation
- `calendar` - Calendar operations
- `woocommerce` - WooCommerce API
- `snowflake` - Snowflake data warehouse

**MCP Integration Pattern** (in config JSON):
```json
{
  "env_class": "gem.envs.ab_testing_s2l.ab_testing_s2l.ABTestingS2LEnv",
  "mcp_servers": {
    "google_cloud": {
      "type": "google_cloud",
      "enabled": true,
      "params": {
        "data_dir": "{task_workspace}/local_db/google_cloud"
      }
    },
    "python_execute": {
      "type": "python_execute",
      "enabled": true,
      "params": {
        "workspace_dir": "{agent_workspace}"
      }
    },
    "claim_done": {
      "type": "claim_done",
      "enabled": true,
      "params": {}
    }
  }
}
```

The `run_multi_openai_v2.py` script automatically sets up MCP servers based on configuration, replacing path placeholders (`{task_workspace}`, `{agent_workspace}`) with actual workspace directories.

### Tool System (Legacy/Training)

For training scenarios (not primary focus), tools integrate via wrappers:

**Tool Classes** (`gem/tools/`):
- `BaseTool` - abstract base class for all tools
- `PythonCodeTool` - executes Python code blocks
- `SearchTool` - performs web searches
- `MCPTool` - interfaces with MCP servers

The `ToolEnvWrapper` intercepts agent actions, parses tool invocations, executes them, and returns tool outputs as observations.

### Wrapper System

Wrappers modify environment behavior via the decorator pattern. Key wrappers (`gem/wrappers/`):

1. **`ObservationWrapper`**: Formats observations for LLMs
   - `include_action`: Concatenates previous action with observation
   - `include_chat_template`: Applies tokenizer chat template (e.g., Qwen format)
   - `apply_chat_template_on_reset`: Apply template only on reset

2. **`EpisodeTrackingWrapper`**: Tracks episode-level statistics

3. **`ToolEnvWrapper`**: Adds tool execution capabilities (see Tool System)

**Wrapper Factory** (`gem/wrappers/wrapper_factory.py`):
- `WRAPPER_FACTORY` dict maps wrapper names to partial functions
- `get_wrapper_fns(wrappers, tokenizer)` creates wrapper list from comma-separated names
- Order matters: tool wrappers → observation wrappers → tracking wrappers

### Vectorized Environments

For parallel rollout generation (`gem/vector/`):

- **`AsyncVectorEnv`**: Thread-pool based parallel execution (recommended for I/O-bound tasks)
- **`SyncVectorEnv`**: Sequential execution (simpler, easier to debug)

**Workspace Isolation**: When using `make_vec` with `root_dir`, each environment gets its own subdirectory (`env_0`, `env_1`, etc.) for isolated file operations. Critical for environments like Canvas that manipulate files.

### Context Management Strategies

The benchmarking suite tests various strategies for managing long contexts:

**Available Strategies** (configured via command-line flags):
- **Context Reset** (`--context_reset`): Truncate old messages when context exceeds threshold
  - `reset_size`: Context size threshold (e.g., 200000 tokens)
  - `reset_ratio`: How much to keep (e.g., 0.5 = keep 50%)
- **Context Summary** (`--context_summary`): Summarize old context instead of truncating
- **Context Awareness** (`--context_awareness`): Track and report context usage to agent
- **Thinking Reset** (`--thinking_reset`): Special handling for reasoning traces
  - `keep_thinking`: How many recent thinking traces to retain
- **Memory Tools**: Use persistent memory MCP servers for long-term storage
- **Max Context Size** (`--max_context_size`): Hard limit on context window
- **Memory Warning Threshold** (`--memory_warning_threshold`): When to warn about context usage

These strategies are tested to understand their impact on:
- Task success rate
- Context window utilization
- Response quality
- Token efficiency

### Training Framework Integration (Secondary Feature)

The `examples/` directory demonstrates integration with 6 RL frameworks for training agents (not the primary focus of this benchmarking project):

- `examples/train_oat/` - Oat (vLLM + DeepSpeed)
- `examples/train_verl/` - Verl (flexible backend support)
- `examples/train_rl2/` - RL2 (SGLang + FSDP)
- `examples/train_tinker/` - Tinker (SDK-based)
- `examples/train_openrlhf/` - OpenRLHF

## Important Patterns

### Creating Benchmark Configurations

The most common task is creating new benchmark configurations:

1. **Create a configuration JSON file** in `inference/`:
```json
{
  "configurations": [
    {
      "env_class": "gem.envs.your_env.your_env.YourEnv",
      "env_params": {
        "param1": "value1",
        "seed": 42
      },
      "mcp_servers": {
        "filesystem": {
          "type": "filesystem",
          "enabled": true,
          "params": {
            "workspace_path": "{agent_workspace}"
          }
        },
        "claim_done": {
          "type": "claim_done",
          "enabled": true,
          "params": {}
        }
      }
    }
  ]
}
```

2. **Validate the configuration**:
```bash
cd inference
python validate_config.py your_config.json
```

3. **Run the benchmark**:
```bash
./run_parallel_test.sh your_config.json 1 5 v2
```

4. **Analyze results**:
```bash
# Results saved to: evals/benchmarks/inf_<timestamp>_<config>_<model>/
cat evals/benchmarks/inf_*/summary-*.json
```

### Registering New Environments

1. Create environment class in `gem/envs/your_env/`:
```python
from gem.core import Env

class MyEnv(Env):
    def __init__(self, **kwargs):
        # initialization

    def reset(self, seed=None):
        # return initial observation and info

    def step(self, action):
        # return obs, reward, terminated, truncated, info
```

2. Register in `gem/envs/__init__.py`:
```python
register(
    "category:MyEnv-v0",
    "gem.envs.my_env:MyEnv",
    param1=value1,
)
```

### Tool Execution Flow

When an agent action contains tool invocations:
1. `ToolEnvWrapper.step()` intercepts the action
2. Each registered tool's `execute_action()` attempts to parse the action
3. If parsed successfully, tool executes and returns observation (tool output)
4. Tool rewards are added to the episode
5. If not parsed or tool limit reached, action is passed to underlying env

### Multi-Environment Training

For environments requiring isolated workspaces (Canvas, terminal, file-based tasks):
```python
env = gem.make_vec(
    env_ids=["canvas:CanvasListTestS2L-v0"] * 4,
    wrappers=[...],
    async_mode=True,
    root_dir="/path/to/workspaces"  # Creates env_0/, env_1/, ...
)
```

Each environment instance gets its own task_dir automatically set to `{root_dir}/env_{idx}`.

## Code Style and Testing

- Python 3.10-3.12 required
- Format: Black (88 char line length), isort, autoflake
- Linting: pylint with custom rules (see `pyproject.toml`)
- Docstrings: Google style
- Type hints: Required for new code (mypy enabled)
- Tests: pytest in `tests/` directory
  - `tests/test_env/` - environment tests
  - `tests/test_tool/` - tool tests
  - Run with `pytest -s` for verbose output

## File Structure Notes

**Core Benchmarking Files**:
- `inference/run_multi_openai_v2.py` - Main parallel inference runner (KEY FILE)
- `inference/run_parallel_test.sh` - Bash wrapper for launching benchmarks (KEY FILE)
- `inference/*.json` - Benchmark configuration files (easy_*, final_* series)
- `inference/validate_config.py` - Configuration validator
- `inference/ana_all_configs.py` - Results analysis tool
- `evals/benchmarks/` - Benchmark results storage (gitignored, generated at runtime)

**Environment Files**:
- `gem/envs/` - One directory per environment (s2l environments are primary focus)
- `gem/envs/__init__.py` - Environment registration
- `gem/envs/*/` - Each env has: main env file, evaluation/, preprocess/, test files

**MCP Server Files**:
- `gem/tools/mcp_server/` - Mock MCP server implementations (KEY DIRECTORY)
- `gem/tools/mcp_server/*/helper.py` - Server setup functions (e.g., `get_canvas_stdio_config()`)
- `gem/tools/mcp_tool.py` - MCP tool wrapper for environments

**Package Metadata**:
- `gem/__about__.py` - version number (update for releases)
- `pyproject.toml` - Package configuration, dependencies, build settings
- `setup.py` - Build script (excludes examples from package)

**Training Examples** (Secondary):
- `examples/` - Training scripts are NOT included in package (see `setup.py` excludes)

## Special Considerations for Benchmarking

1. **Workspace Isolation**: Each benchmark run gets isolated workspaces:
   - `task_workspace` - Environment-specific data (read-only, seeded data)
   - `agent_workspace` - Agent's working directory (writable, for intermediate files)
   - Path placeholders `{task_workspace}` and `{agent_workspace}` auto-replaced in configs

2. **Configuration Files Naming Convention**:
   - `easy_*k_set_config*.json` - Easier tasks, varying context lengths
   - `final_*k_set_config*.json` - Final benchmark suite, varying context lengths
   - `*_multi_seed.json` - Multiple runs with different seeds
   - `*_ptc.json` - With programmatic tool calling
   - `*_memory.json` - With memory tool enabled

3. **Context Length Estimation**: Use `inference/estimate_length.py` to estimate context requirements for configurations before running full benchmarks.

4. **Parallel Execution**: The benchmarking suite uses ProcessPoolExecutor for parallel execution. Adjust `max_workers` based on:
   - Available CPU cores
   - API rate limits
   - Memory constraints per worker

5. **Resume Mode**: Use `--resume_dir` to resume failed benchmark runs from existing output directory. Only failed configurations are re-executed.

6. **MCP Server Isolation**: Each environment instance gets its own MCP server processes. Servers are automatically started/stopped per episode.

7. **Model Integration**: The suite supports:
   - OpenAI API (GPT-4, GPT-5, o1 series)
   - Anthropic API (Claude models)
   - OpenRouter (various models)
   - Custom endpoints (set `API_KEY` and `MODEL` in `run_parallel_test.sh`)

8. **Context Management Testing**: When testing context strategies, be aware:
   - `context_reset=True` may lose critical information but saves tokens
   - `context_summary=True` is expensive (extra API calls) but preserves information
   - Memory tools provide explicit long-term storage but require agent to use them

## Release Preparation Notes

This project is ready for refactoring for official release. Key areas to focus on:

1. **Code Organization**: Consolidate similar environments, remove duplicate code
2. **Documentation**: Add docstrings, API documentation, usage examples
3. **Testing**: Expand test coverage in `tests/`, add integration tests
4. **Configuration Validation**: Enhance `validate_config.py` with better error messages
5. **Results Analysis**: Improve `ana_all_configs.py` with visualization and statistics
6. **MCP Server Documentation**: Document each MCP server's API and usage
7. **Benchmark Suite**: Finalize and document the standard benchmark configurations
8. **License and Credits**: Ensure all files have proper license headers
