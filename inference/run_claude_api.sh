#!/bin/bash

# Claude API Parallel Inference Runner Script (Clean Version)
#
# This script runs inference using Claude API with various configuration options.
# It supports extended thinking, context management, and programmatic tool calling.
#
# Usage:
#   ./run_claude_api_clean.sh --config-file CONFIG.json [OPTIONS]
#
# ============================================================================
# REQUIRED PARAMETERS
# ============================================================================
#
#   --strategy STRATEGY         Inference strategy (default: react)
#                               Options: react, ptc, memory_tool, debug, claude_api
#   --config-file PATH          Configuration JSON filename (not full path)
#                               Default: final_128k_set_config_multi_seed.json
#
# ============================================================================
# GENERAL PARAMETERS
# ============================================================================
#
#   --runs-per-config NUM       Number of runs per config (default: 1)
#   --max-workers NUM           Number of parallel workers (default: 20)
#   --model MODEL               Claude model name (default: claude-opus-4-5-20251101)
#   --max-tokens NUM            Max tokens for generation (default: 32768)
#   --max-tool-uses NUM         Max tool uses per conversation (default: 500)
#   --max-context-size NUM      Max context window size in tokens (default: 200000)
#   --group-by-seed BOOL        Group results by seed (default: True)
#   --base-url URL              Claude API base URL (default: https://openai.app.msh.team/)
#   --api-key KEY               Claude API key (default: from ANTHROPIC_API_KEY env)
#
# ============================================================================
# EXTENDED THINKING PARAMETERS
# ============================================================================
#
#   --enable-thinking BOOL      Enable extended thinking mode (default: False)
#   --thinking-budget NUM       Thinking budget in tokens (default: 10000)
#
# ============================================================================
# CONTEXT MANAGEMENT PARAMETERS
# ============================================================================
#
#   --clear-tool-uses BOOL      Enable tool use clearing (default: False)
#   --clear-threshold NUM       Token threshold for clearing (default: 50000)
#   --clear-keep NUM            Number of tool uses to keep (default: 3)
#   --clear-min-tokens NUM      Minimum tokens to clear (default: 20000)
#
#   --clear-thinking BOOL       Enable thinking clearing (default: False)
#   --keep-thinking-turns NUM   Number of thinking turns to keep (default: 2)
#
# ============================================================================
# TOOL CALLING PARAMETERS
# ============================================================================
#
#   --enable-code-exec BOOL     Enable code execution (default: True)
#   --programmatic-calling BOOL Enable programmatic tool calling (default: True)
#
# ============================================================================
# BEHAVIORAL PARAMETERS
# ============================================================================
#
#   --background                Run in background mode with nohup
#   --dry-run                   Show configuration without running
#   --quiet                     Suppress verbose output
#
# ============================================================================
# EXAMPLES
# ============================================================================
#
#   # Basic run with default settings
#   ./run_claude_api_clean.sh --strategy react --config-file final_128k_set_config_multi_seed.json
#
#   # Quick test run
#   ./run_claude_api_clean.sh --strategy claude_api --config-file final_8k_set_config_multi_seed.json --runs-per-config 1 --max-workers 1
#
#   # Extended thinking with context management
#   ./run_claude_api_clean.sh --strategy debug --config-file final_8k_set_config_multi_seed.json \
#     --enable-thinking True --thinking-budget 15000 \
#     --clear-tool-uses True --clear-threshold 60000
#
#   # Background execution
#   ./run_claude_api_clean.sh --strategy claude_api --config-file final_8k_set_config_multi_seed.json --background
#
# ============================================================================

set -euo pipefail

# Determine script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ============================================================================
# Default Values
# ============================================================================

# Required parameters
STRATEGY="react"
CONFIG_FILE="debug.json"

# General parameters
RUNS_PER_CONFIG="1"
MAX_WORKERS="20"
MODEL="claude-opus-4-5-20251101"
MAX_TOKENS="32768"
MAX_TOOL_USES="500"
MAX_CONTEXT_SIZE="200000"
GROUP_BY_SEED="True"
BASE_URL=""
API_KEY=""

# Extended thinking parameters
ENABLE_THINKING="False"
THINKING_BUDGET="10000"

# Context management parameters
CLEAR_TOOL_USES="False"
CLEAR_THRESHOLD="50000"
CLEAR_KEEP="3"
CLEAR_MIN_TOKENS="20000"
CLEAR_THINKING="False"
KEEP_THINKING_TURNS="2"

# Tool calling parameters
ENABLE_CODE_EXEC="False"
PROGRAMMATIC_CALLING="False"

# Behavioral parameters
BACKGROUND="False"
DRY_RUN="False"
QUIET="False"

# ============================================================================
# Parse Command Line Arguments
# ============================================================================

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
        --model)
            MODEL="$2"
            shift 2
            ;;
        --max-tokens)
            MAX_TOKENS="$2"
            shift 2
            ;;
        --max-tool-uses)
            MAX_TOOL_USES="$2"
            shift 2
            ;;
        --max-context-size)
            MAX_CONTEXT_SIZE="$2"
            shift 2
            ;;
        --group-by-seed)
            GROUP_BY_SEED="$2"
            shift 2
            ;;
        --base-url)
            BASE_URL="$2"
            shift 2
            ;;
        --api-key)
            API_KEY="$2"
            shift 2
            ;;
        --enable-thinking)
            ENABLE_THINKING="$2"
            shift 2
            ;;
        --thinking-budget)
            THINKING_BUDGET="$2"
            shift 2
            ;;
        --clear-tool-uses)
            CLEAR_TOOL_USES="$2"
            shift 2
            ;;
        --clear-threshold)
            CLEAR_THRESHOLD="$2"
            shift 2
            ;;
        --clear-keep)
            CLEAR_KEEP="$2"
            shift 2
            ;;
        --clear-min-tokens)
            CLEAR_MIN_TOKENS="$2"
            shift 2
            ;;
        --clear-thinking)
            CLEAR_THINKING="$2"
            shift 2
            ;;
        --keep-thinking-turns)
            KEEP_THINKING_TURNS="$2"
            shift 2
            ;;
        --enable-code-exec)
            ENABLE_CODE_EXEC="$2"
            shift 2
            ;;
        --programmatic-calling)
            PROGRAMMATIC_CALLING="$2"
            shift 2
            ;;
        --background)
            BACKGROUND="True"
            shift
            ;;
        --dry-run)
            DRY_RUN="True"
            shift
            ;;
        --quiet)
            QUIET="True"
            shift
            ;;
        --help)
            sed -n '3,/^$/p' "$0" | sed 's/^# //' | sed 's/^#//'
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ============================================================================
# Validate Configuration
# ============================================================================

# Validate required parameters
if [ -z "$CONFIG_FILE" ]; then
    echo "Error: --config-file is required"
    echo "Use --help for usage information"
    exit 1
fi

# Set API key from environment or parameter
if [ -z "$API_KEY" ]; then
    API_KEY="${ANTHROPIC_API_KEY:-}"
fi

if [ -z "$API_KEY" ]; then
    echo "Error: API key not provided"
    echo "Please provide API key via --api-key or set ANTHROPIC_API_KEY environment variable"
    exit 1
fi

# Validate strategy parameter
if [[ "$STRATEGY" != "react" && "$STRATEGY" != "ptc" && "$STRATEGY" != "memory_tool" && "$STRATEGY" != "debug" && "$STRATEGY" != "claude_api" ]]; then
    echo "Error: Invalid strategy '$STRATEGY'"
    echo "Valid strategies: react, ptc, memory_tool, debug, claude_api"
    exit 1
fi

# Sanitize model name for use in file/directory paths (replace / with -)
MODEL_SAFE="${MODEL//\//-}"

# Determine strategy directory
STRATEGY_DIR="$SCRIPT_DIR/$STRATEGY"

# Check if strategy directory exists
if [ ! -d "$STRATEGY_DIR" ]; then
    echo "Error: Strategy directory not found: $STRATEGY_DIR"
    echo "Available strategies: react, ptc, memory_tool, debug, claude_api"
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
    echo "Available configs in $SCRIPT_DIR:"
    ls -1 "$SCRIPT_DIR"/*.json 2>/dev/null || echo "  No JSON files found"
    exit 1
fi

# ============================================================================
# Setup Environment
# ============================================================================

# Set environment variables
export ANTHROPIC_BASE_URL="$BASE_URL"
export ANTHROPIC_API_KEY="$API_KEY"
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/mcp_convert:${PYTHONPATH:-}"

# Setup directories
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
MODEL_SAFE="${MODEL//\//-}"
PARAM_SUFFIX="_${MODEL_SAFE}_MT${MAX_TOOL_USES}"

# Output directory (permanent storage)
OUTPUT_DIR="$PROJECT_ROOT/evals/benchmarks/claude_api_${TIMESTAMP}_${CONFIG_FILE}${PARAM_SUFFIX}"

# Base task directory inside output directory (no tmp storage)
BASE_TASK_DIR="$OUTPUT_DIR/tasks"

# Logs directory
LOGS_DIR="$PROJECT_ROOT/inference/logs"
mkdir -p "$LOGS_DIR"
LOG_FILE="$LOGS_DIR/claude_api_${TIMESTAMP}_${CONFIG_FILE}${PARAM_SUFFIX}.log"

# Create directories
mkdir -p "$BASE_TASK_DIR"
mkdir -p "$OUTPUT_DIR"

# ============================================================================
# Build Command
# ============================================================================

CMD_ARGS=(
    "--config_file" "$FULL_CONFIG_PATH"
    "--runs_per_config" "$RUNS_PER_CONFIG"
    "--max_workers" "$MAX_WORKERS"
    "--max_tool_uses" "$MAX_TOOL_USES"
    "--max_tokens" "$MAX_TOKENS"
    "--model" "$MODEL"
    "--group_by_seed" "$GROUP_BY_SEED"
    "--enable_thinking" "$ENABLE_THINKING"
    "--thinking_budget_tokens" "$THINKING_BUDGET"
    "--use_clear_tool_uses" "$CLEAR_TOOL_USES"
    "--clear_trigger_tokens" "$CLEAR_THRESHOLD"
    "--clear_keep_tool_uses" "$CLEAR_KEEP"
    "--clear_at_least_tokens" "$CLEAR_MIN_TOKENS"
    "--use_clear_thinking" "$CLEAR_THINKING"
    "--clear_keep_thinking_turns" "$KEEP_THINKING_TURNS"
    "--enable_code_execution" "$ENABLE_CODE_EXEC"
    "--enable_programmatic_tool_calling" "$PROGRAMMATIC_CALLING"
    "--base_task_dir" "$BASE_TASK_DIR"
    "--output_dir" "$OUTPUT_DIR"
    "--max_context_size" "$MAX_CONTEXT_SIZE"
)

# ============================================================================
# Display Configuration
# ============================================================================

if [ "$QUIET" != "True" ]; then
    echo "=================================================================================="
    echo "Claude API Parallel Inference Configuration"
    echo "=================================================================================="
    echo "Configuration:"
    echo "  Strategy:          $STRATEGY"
    echo "  Config file:       $FULL_CONFIG_PATH"
    echo "  Runs per config:   $RUNS_PER_CONFIG"
    echo "  Max workers:       $MAX_WORKERS"
    echo "  "
    echo "Model Configuration:"
    echo "  Model:             $MODEL"
    echo "  Max tokens:        $MAX_TOKENS"
    echo "  Max tool uses:     $MAX_TOOL_USES"
    echo "  Max context:       $MAX_CONTEXT_SIZE"
    echo "  Group by seed:     $GROUP_BY_SEED"
    echo "  "
    echo "Extended Thinking:"
    echo "  Enabled:           $ENABLE_THINKING"
    if [ "$ENABLE_THINKING" = "True" ]; then
        echo "  Budget tokens:     $THINKING_BUDGET"
    fi
    echo "  "
    echo "Context Management:"
    echo "  Tool use clearing: $CLEAR_TOOL_USES"
    if [ "$CLEAR_TOOL_USES" = "True" ]; then
        echo "    Threshold:       $CLEAR_THRESHOLD"
        echo "    Keep:            $CLEAR_KEEP"
        echo "    Min tokens:      $CLEAR_MIN_TOKENS"
    fi
    echo "  Thinking clearing: $CLEAR_THINKING"
    if [ "$CLEAR_THINKING" = "True" ]; then
        echo "    Keep turns:      $KEEP_THINKING_TURNS"
    fi
    echo "  "
    echo "Tool Calling:"
    echo "  Code execution:    $ENABLE_CODE_EXEC"
    echo "  Programmatic:      $PROGRAMMATIC_CALLING"
    echo "  "
    echo "Directories:"
    echo "  Tasks:             $BASE_TASK_DIR"
    echo "  Outputs:           $OUTPUT_DIR"
    echo "  Log:               $LOG_FILE"
    echo "=================================================================================="
    echo ""
fi

# ============================================================================
# Execute or Dry Run
# ============================================================================

if [ "$DRY_RUN" = "True" ]; then
    echo "Dry run mode - configuration validated successfully"
    echo ""
    echo "Python command that would be executed:"
    echo "cd $PROJECT_ROOT && python $SCRIPT_DIR/run_claude_api.py ${CMD_ARGS[*]}"
    exit 0
fi

# Change to project root
cd "$PROJECT_ROOT" || exit 1

# Run command
PYTHON_CMD="python $SCRIPT_DIR/run_claude_api.py ${CMD_ARGS[*]}"

if [ "$BACKGROUND" = "True" ]; then
    # Background execution
    nohup $PYTHON_CMD > "$LOG_FILE" 2>&1 &
    PID=$!

    # Save PID
    PID_FILE="$LOGS_DIR/claude_api_${TIMESTAMP}.pid"
    echo $PID > "$PID_FILE"

    echo "Process started in background with PID: $PID"
    echo "PID saved to: $PID_FILE"
    echo "Log file: $LOG_FILE"
    echo ""
    echo "To monitor progress: tail -f $LOG_FILE"
    echo "To stop the process: kill $PID"
else
    # Foreground execution
    $PYTHON_CMD
fi

echo ""
echo "✓ Configuration completed successfully!"