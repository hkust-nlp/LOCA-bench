#!/bin/bash

# Parallel Inference Runner Script (Clean Version)
#
# This script supports multiple context management strategies for long-context agentic tasks.
#
# Usage:
#   ./run.sh --config-file CONFIG.json [OPTIONS]
#
# ============================================================================
# CONTEXT MANAGEMENT STRATEGIES
# ============================================================================
#
# 1. ReAct (Base Strategy - Default)
#    Basic reactive agent without special context management
#    Config location: inference/react/
#
# 2. Programmatic Tool Calling (PTC)
#    Orchestrate tools by executing code rather than individual tool calls
#    Config location: inference/ptc/
#    Enabled by: --strategy ptc
#
# 3. Memory Tool
#    Persistent storage and retrieval across conversations
#    Config location: inference/memory_tool/
#    Enabled by: --strategy memory_tool
#
# ============================================================================
# REQUIRED PARAMETERS
# ============================================================================
#
#   --config-file PATH          Configuration JSON filename (not full path)
#                               The script will look in the strategy directory
#
# ============================================================================
# GENERAL PARAMETERS
# ============================================================================
#
#   --strategy STRATEGY         Context management strategy (default: react)
#                               Options: react, ptc, memory_tool
#   --runs-per-config NUM       Number of runs per config (default: 1)
#   --max-workers NUM           Number of parallel workers (default: 5)
#   --api-key KEY               OpenAI API key (default: from OPENAI_API_KEY env)
#   --base-url URL              API base URL (default: https://api.openai.com/v1)
#   --model MODEL               Model name (default: gpt-5-nano)
#   --max-tokens NUM            Max tokens for generation (default: 32768)
#   --max-context-size NUM      Max context window size (default: 128000)
#   --group-by-seed BOOL        Group results by seed (default: True)
#   --resume PATH|true          Resume from directory or auto-construct path (default: empty)
#
# ============================================================================
# CONTEXT EDITING PARAMETERS (Tool-result & Thinking-block Clearing)
# ============================================================================
#
#   --context-reset BOOL        Enable context reset - removes past tool outputs
#                               when context exceeds threshold (default: False)
#   --reset-size NUM            Context threshold in tokens for reset (default: 200000)
#   --reset-ratio NUM           Ratio of context to keep after reset 0.0-1.0 (default: 0.5)
#
#   --thinking-reset BOOL       Enable thinking-block clearing - removes prior
#                               reasoning content after threshold (default: False)
#   --keep-thinking NUM         Number of recent thinking traces to retain (default: 1)
#
# ============================================================================
# CONTEXT COMPACTION PARAMETERS (Summarization)
# ============================================================================
#
#   --context-summary BOOL      Enable context compaction - prompts model to
#                               summarize conversation history (default: False)
#
# ============================================================================
# CONTEXT AWARENESS PARAMETERS (Real-time Feedback)
# ============================================================================
#
#   --context-awareness BOOL    Enable context awareness - provides real-time
#                               feedback on remaining context capacity (default: False)
#   --memory-warning-threshold NUM  Threshold for memory warnings 0.0-1.0 (default: 0.5)
#
# ============================================================================
# REASONING PARAMETERS (for reasoning models like o1, o3)
# ============================================================================
#
#   --reasoning-effort LEVEL    Reasoning effort: none|minimal|low|medium|high|xhigh (default: empty)
#   --reasoning-max-tokens NUM  Reasoning token limit (default: empty)
#   --reasoning-enabled BOOL    Enable reasoning (default: True)
#   --reasoning-exclude BOOL    Exclude reasoning tokens from context (default: False)
#
# ============================================================================
# EXAMPLES
# ============================================================================
#
#   # Basic ReAct run (default strategy)
#   ./run.sh --config-file final_8k_set_config_multi_seed.json
#
#   # Use Programmatic Tool Calling strategy
#   ./run.sh --strategy ptc --config-file final_8k_set_config_multi_seed_ptc.json
#
#   # Use Memory Tool strategy
#   ./run.sh --strategy memory_tool --config-file final_64k_set_config_multi_seed_memory.json
#
#   # Enable context editing (tool-result clearing)
#   ./run.sh --config-file my_config.json --context-reset True --reset-size 100000
#
#   # Enable context compaction (summarization)
#   ./run.sh --config-file my_config.json --context-summary True
#
#   # Enable context awareness
#   ./run.sh --config-file my_config.json --context-awareness True --memory-warning-threshold 0.8
#
#   # Multiple context management techniques
#   ./run.sh --config-file my_config.json \
#     --context-reset True --context-summary True --context-awareness True
#
#   # Resume a previous run
#   ./run.sh --config-file my_config.json --resume true
#
# ============================================================================
# PREREQUISITES
# ============================================================================
#
# 1. Install the gem-llm package:
#    pip install -e .
#    OR
#    pip install gem-llm
#
# 2. Ensure mcp-convert directory exists at project root
#    (contains the mcps module required for MCP tool servers)
#
# 3. Set up API credentials:
#    export OPENAI_API_KEY=your_key_here
#    OR
#    Use --api-key flag when running
#
# ============================================================================

# Determine script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ============================================================================
# Default Values
# ============================================================================

# General parameters
STRATEGY="react"
CONFIG_FILE="final_96k_set_config_multi_seed.json"
RUNS_PER_CONFIG="1"
MAX_WORKERS="15"
API_KEY=""
BASE_URL="https://openai.app.msh.team/v1"
MODEL="x35-0121-zwh"
MAX_TOKENS="32768"
MAX_CONTEXT_SIZE="260000"
GROUP_BY_SEED="True"
RESUME=""

# Context Editing parameters (tool-result & thinking-block clearing)
CONTEXT_RESET="False"
RESET_SIZE="200000"
RESET_RATIO="0.5"
THINKING_RESET="False"
KEEP_THINKING="1"

# Context Compaction parameters (summarization)
CONTEXT_SUMMARY="False"

# Context Awareness parameters (real-time feedback)
CONTEXT_AWARENESS="False"
MEMORY_WARNING_THRESHOLD="0.5"

# Reasoning parameters
REASONING_EFFORT=""
REASONING_MAX_TOKENS=""
REASONING_ENABLED="True"
REASONING_EXCLUDE="False"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --strategy)
            STRATEGY="$2"
            shift 2
            ;;
        --config-file)
            CONFIG_FILE="$2"
            shift 2
            ;;
        --runs-per-config)
            RUNS_PER_CONFIG="$2"
            shift 2
            ;;
        --max-workers)
            MAX_WORKERS="$2"
            shift 2
            ;;
        --api-key)
            API_KEY="$2"
            shift 2
            ;;
        --base-url)
            BASE_URL="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --max-tokens)
            MAX_TOKENS="$2"
            shift 2
            ;;
        --context-reset)
            CONTEXT_RESET="$2"
            shift 2
            ;;
        --context-summary)
            CONTEXT_SUMMARY="$2"
            shift 2
            ;;
        --context-awareness)
            CONTEXT_AWARENESS="$2"
            shift 2
            ;;
        --reset-size)
            RESET_SIZE="$2"
            shift 2
            ;;
        --reset-ratio)
            RESET_RATIO="$2"
            shift 2
            ;;
        --max-context-size)
            MAX_CONTEXT_SIZE="$2"
            shift 2
            ;;
        --memory-warning-threshold)
            MEMORY_WARNING_THRESHOLD="$2"
            shift 2
            ;;
        --thinking-reset)
            THINKING_RESET="$2"
            shift 2
            ;;
        --keep-thinking)
            KEEP_THINKING="$2"
            shift 2
            ;;
        --reasoning-effort)
            REASONING_EFFORT="$2"
            shift 2
            ;;
        --reasoning-max-tokens)
            REASONING_MAX_TOKENS="$2"
            shift 2
            ;;
        --reasoning-enabled)
            REASONING_ENABLED="$2"
            shift 2
            ;;
        --reasoning-exclude)
            REASONING_EXCLUDE="$2"
            shift 2
            ;;
        --group-by-seed)
            GROUP_BY_SEED="$2"
            shift 2
            ;;
        --resume)
            RESUME="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$CONFIG_FILE" ]; then
    echo "Error: --config-file is required"
    echo ""
    echo "Usage: ./run.sh --config-file CONFIG.json [OPTIONS]"
    echo "Run './run.sh --help' for more information"
    exit 1
fi

# Validate strategy parameter
if [[ "$STRATEGY" != "react" && "$STRATEGY" != "ptc" && "$STRATEGY" != "memory_tool" ]]; then
    echo "Error: Invalid strategy '$STRATEGY'"
    echo "Valid strategies: react, ptc, memory_tool"
    exit 1
fi

# Sanitize model name for use in file/directory paths (replace / with -)
MODEL_SAFE="${MODEL//\//-}"

# Determine strategy directory
STRATEGY_DIR="$SCRIPT_DIR/$STRATEGY"

# Check if strategy directory exists
if [ ! -d "$STRATEGY_DIR" ]; then
    echo "Error: Strategy directory not found: $STRATEGY_DIR"
    echo "Available strategies: react, ptc, memory_tool"
    exit 1
fi

# Determine full config path
if [[ "$CONFIG_FILE" = /* ]]; then
    # Absolute path provided
    FULL_CONFIG_PATH="$CONFIG_FILE"
else
    # Relative path - look in strategy directory
    FULL_CONFIG_PATH="$STRATEGY_DIR/$CONFIG_FILE"
fi

# Check if config file exists
if [ ! -f "$FULL_CONFIG_PATH" ]; then
    echo "Error: Config file not found: $FULL_CONFIG_PATH"
    echo "Available configs in $STRATEGY_DIR:"
    ls -1 "$STRATEGY_DIR"/*.json 2>/dev/null || echo "  No JSON files found"
    exit 1
fi

# Extract config file basename (without path and extension)
CONFIG_BASENAME=$(basename "$CONFIG_FILE" .json)

# Build parameter suffix for directory name
PARAM_SUFFIX=""
[ "$CONTEXT_RESET" = "True" ] && PARAM_SUFFIX="${PARAM_SUFFIX}_CR"
[ "$CONTEXT_SUMMARY" = "True" ] && PARAM_SUFFIX="${PARAM_SUFFIX}_CS"
[ "$CONTEXT_AWARENESS" = "True" ] && PARAM_SUFFIX="${PARAM_SUFFIX}_CA"
[ "$THINKING_RESET" = "True" ] && PARAM_SUFFIX="${PARAM_SUFFIX}_TR"
PARAM_SUFFIX="${PARAM_SUFFIX}_RS${RESET_SIZE}_RR${RESET_RATIO}_MC${MAX_CONTEXT_SIZE}_MW${MEMORY_WARNING_THRESHOLD}"
[ "$THINKING_RESET" = "True" ] && PARAM_SUFFIX="${PARAM_SUFFIX}_KT${KEEP_THINKING}"
if [ -n "$REASONING_EFFORT" ]; then
    PARAM_SUFFIX="${PARAM_SUFFIX}_RE${REASONING_EFFORT}"
elif [ -n "$REASONING_MAX_TOKENS" ]; then
    PARAM_SUFFIX="${PARAM_SUFFIX}_RT${REASONING_MAX_TOKENS}"
fi

# Setup directories with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Handle resume mode
if [ -n "$RESUME" ]; then
    if [ "$RESUME" = "true" ]; then
        # Auto-construct resume path
        OUTPUT_DIR="$PROJECT_ROOT/evals/benchmarks/inf_${STRATEGY}_${CONFIG_BASENAME}_${MODEL_SAFE}${PARAM_SUFFIX}"
    else
        # Use provided path
        OUTPUT_DIR="$RESUME"
    fi

    if [ ! -d "$OUTPUT_DIR" ]; then
        echo "Error: Resume directory does not exist: $OUTPUT_DIR"
        exit 1
    fi

    echo "RESUME MODE: Using existing output directory: $OUTPUT_DIR"
else
    # Create new output directory (with timestamp, includes strategy)
    OUTPUT_DIR="$PROJECT_ROOT/evals/benchmarks/inf_${STRATEGY}_${CONFIG_BASENAME}_${MODEL_SAFE}${PARAM_SUFFIX}_${TIMESTAMP}"
fi

# Base task directory inside output directory
BASE_TASK_DIR="$OUTPUT_DIR/tasks"

mkdir -p "$BASE_TASK_DIR"
mkdir -p "$OUTPUT_DIR"

# Set environment variables
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/mcp-convert:$PYTHONPATH"

# Change to project root for execution
cd "$PROJECT_ROOT" || exit 1


# Print configuration
echo "=================================================================================="
if [ -n "$RESUME" ]; then
    echo "Starting Parallel Inference (RESUME MODE)"
else
    echo "Starting Parallel Inference"
fi
echo "=================================================================================="
echo "Strategy:          $STRATEGY"
echo "Config file:       $FULL_CONFIG_PATH"
echo "Runs per config:   $RUNS_PER_CONFIG"
echo "Max workers:       $MAX_WORKERS"
echo ""
echo "Model Configuration:"
echo "  Base URL:        $BASE_URL"
echo "  Model:           $MODEL"
echo "  Max tokens:      $MAX_TOKENS"
echo "  Max context:     $MAX_CONTEXT_SIZE"
echo ""
echo "Context Management Strategies:"
echo "  [Context Editing - Tool-result Clearing]"
echo "    Reset:         $CONTEXT_RESET"
if [ "$CONTEXT_RESET" = "True" ]; then
echo "    Reset size:    $RESET_SIZE"
echo "    Reset ratio:   $RESET_RATIO"
fi
echo "  [Context Editing - Thinking-block Clearing]"
echo "    Thinking reset: $THINKING_RESET"
if [ "$THINKING_RESET" = "True" ]; then
echo "    Keep thinking: $KEEP_THINKING"
fi
echo "  [Context Compaction]"
echo "    Summary:       $CONTEXT_SUMMARY"
echo "  [Context Awareness]"
echo "    Awareness:     $CONTEXT_AWARENESS"
if [ "$CONTEXT_AWARENESS" = "True" ]; then
echo "    Memory warning: $MEMORY_WARNING_THRESHOLD"
fi
echo ""
echo "Directories:"
echo "  Strategy:        $STRATEGY_DIR"
echo "  Tasks:           $BASE_TASK_DIR"
echo "  Outputs:         $OUTPUT_DIR"
echo "=================================================================================="
echo ""

# Build resume argument
RESUME_ARG=""
if [ -n "$RESUME" ]; then
    RESUME_ARG="--resume_dir $OUTPUT_DIR"
fi

# Run the inference
python "$SCRIPT_DIR/run_red.py" \
    --config_file "$FULL_CONFIG_PATH" \
    --runs_per_config "$RUNS_PER_CONFIG" \
    --max_workers "$MAX_WORKERS" \
    --api_key "$API_KEY" \
    --base_url "$BASE_URL" \
    --model "$MODEL" \
    --base_task_dir "$BASE_TASK_DIR" \
    --output_dir "$OUTPUT_DIR" \
    --context_reset "$CONTEXT_RESET" \
    --context_summary "$CONTEXT_SUMMARY" \
    --context_awareness "$CONTEXT_AWARENESS" \
    --reset_size "$RESET_SIZE" \
    --reset_ratio "$RESET_RATIO" \
    --group_by_seed "$GROUP_BY_SEED" \
    --max_context_size "$MAX_CONTEXT_SIZE" \
    --memory_warning_threshold "$MEMORY_WARNING_THRESHOLD" \
    --thinking_reset "$THINKING_RESET" \
    --keep_thinking "$KEEP_THINKING" \
    --reasoning_effort "$REASONING_EFFORT" \
    --reasoning_max_tokens "$REASONING_MAX_TOKENS" \
    --reasoning_enabled "$REASONING_ENABLED" \
    --reasoning_exclude "$REASONING_EXCLUDE" \
    --max_tokens "$MAX_TOKENS" \
    $RESUME_ARG

echo ""
echo "=================================================================================="
echo "Inference completed!"
echo "Results saved to: $OUTPUT_DIR"
echo "=================================================================================="
