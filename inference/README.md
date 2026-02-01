# Parallel Inference Runner - Quick Start

A script for running parallel inference with multiple context management strategies for long-context agentic tasks.

## Prerequisites

1. **Install the gem-llm package:**
   ```bash
   pip install -e .
   # OR
   pip install gem-llm
   ```

2. **Ensure `mcp-convert` directory exists** at project root (contains the mcps module for MCP tool servers)

3. **Set up API credentials:**
   ```bash
   export OPENAI_API_KEY=your_key_here
   # OR use --api-key flag when running
   ```

## Basic Usage

```bash
./run.sh --config-file CONFIG.json [OPTIONS]
```

## Context Management Strategies

| Strategy | Description | Config Location |
|----------|-------------|-----------------|
| `react` (default) | Basic reactive agent | `inference/react/` |
| `ptc` | Programmatic Tool Calling - orchestrate tools via code | `inference/ptc/` |
| `memory_tool` | Persistent storage and retrieval across conversations | `inference/memory_tool/` |

## Quick Examples

### Basic ReAct Run
```bash
./run.sh --config-file final_8k_set_config_multi_seed.json
```

### Use Different Strategy
```bash
./run.sh --strategy ptc --config-file final_8k_set_config_multi_seed_ptc.json
./run.sh --strategy memory_tool --config-file final_64k_set_config_multi_seed_memory.json
```

### Custom Model Configuration
```bash
./run.sh --config-file my_config.json \
    --model gpt-4o \
    --base-url https://api.openai.com/v1 \
    --max-tokens 32768 \
    --max-context-size 128000
```

### Enable Context Management Techniques
```bash
# Context editing (tool-result clearing)
./run.sh --config-file my_config.json --context-reset True --reset-size 100000

# Context compaction (summarization)
./run.sh --config-file my_config.json --context-summary True

# Context awareness (real-time feedback)
./run.sh --config-file my_config.json --context-awareness True --memory-warning-threshold 0.8

# Combine multiple techniques
./run.sh --config-file my_config.json \
    --context-reset True --context-summary True --context-awareness True
```

### Resume a Previous Run
```bash
./run.sh --config-file my_config.json --resume true
```

## Common Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--config-file` | Configuration JSON filename (required) | - |
| `--strategy` | Context strategy: react, ptc, memory_tool | `react` |
| `--model` | Model name | `gpt-5-nano` |
| `--base-url` | API base URL | `https://api.openai.com/v1` |
| `--max-workers` | Number of parallel workers | `5` |
| `--runs-per-config` | Number of runs per config | `1` |
| `--max-tokens` | Max tokens for generation | `32768` |
| `--max-context-size` | Max context window size | `128000` |

## Context Management Parameters

### Context Editing (Tool-result Clearing)
| Parameter | Description | Default |
|-----------|-------------|---------|
| `--context-reset` | Enable context reset | `False` |
| `--reset-size` | Token threshold for reset | `200000` |
| `--reset-ratio` | Ratio of context to keep (0.0-1.0) | `0.5` |

### Context Editing (Thinking-block Clearing)
| Parameter | Description | Default |
|-----------|-------------|---------|
| `--thinking-reset` | Enable thinking-block clearing | `False` |
| `--keep-thinking` | Number of recent traces to retain | `1` |

### Context Compaction
| Parameter | Description | Default |
|-----------|-------------|---------|
| `--context-summary` | Enable summarization | `False` |

### Context Awareness
| Parameter | Description | Default |
|-----------|-------------|---------|
| `--context-awareness` | Enable real-time feedback | `False` |
| `--memory-warning-threshold` | Warning threshold (0.0-1.0) | `0.5` |

## Reasoning Parameters (for o1, o3 models)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--reasoning-effort` | none\|minimal\|low\|medium\|high\|xhigh | - |
| `--reasoning-max-tokens` | Reasoning token limit | - |
| `--reasoning-enabled` | Enable reasoning | `True` |
| `--reasoning-exclude` | Exclude reasoning from context | `False` |

## Output

Results are saved to:
```
PROJECT_ROOT/evals/benchmarks/inf_{strategy}_{config_name}_{model}{params}/
```

Task files are stored in:
```
PROJECT_ROOT/mcp_outputs/tasks_{config_name}_{model}{params}/
```
