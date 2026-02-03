#!/bin/bash

# Claude Agent Parallel Inference Runner Script (OpenRouter / Custom Endpoint Version)
#
# This script runs inference using Claude Agent with OpenRouter or other custom endpoints.
# It supports context management via the Claude Code SDK.
#
# Usage:
#   ./run_claude_agent_openrouter.sh --config-file CONFIG.json [OPTIONS]
#
# ============================================================================
# OPENROUTER CONFIGURATION
# ============================================================================
#
# This script supports custom API endpoints (e.g., OpenRouter) via environment
# variables as described in Claude Code SDK authentication.
#
# IMPORTANT for OpenRouter:
#   - Use ANTHROPIC_BASE_URL="https://openrouter.ai/api" (NOT /api/v1)
#   - Use ANTHROPIC_AUTH_TOKEN for the OpenRouter API key
#   - Set ANTHROPIC_API_KEY="" (empty string) to prevent Anthropic fallback
#
# Environment variables (can be overridden by command line options):
#   ANTHROPIC_BASE_URL            - Custom API endpoint
#   ANTHROPIC_AUTH_TOKEN          - OpenRouter API key (sk-or-v1-...)
#   ANTHROPIC_API_KEY             - Must be empty string for OpenRouter
#   ANTHROPIC_MODEL               - Main model (e.g., anthropic/claude-sonnet-4)
#   ANTHROPIC_DEFAULT_HAIKU_MODEL - Fast model (e.g., anthropic/claude-3-haiku)
#
# Reference: https://openrouter.ai/docs/guides/guides/claude-code-integration
#
# ============================================================================
# GENERAL PARAMETERS
# ============================================================================
#
#   --strategy STRATEGY         Strategy directory name (default: claude_agent)
#   --config-file PATH          Configuration JSON filename (not full path)
#                               The script will look in the strategy directory
#                               Default: final_8k_set_config_multi_seed.json
#   --runs-per-config NUM       Number of runs per config (default: 1)
#   --max-workers NUM           Number of parallel workers (default: 20)
#   --max-tool-uses NUM         Max tool uses per conversation (default: 100)
#   --group-by-seed BOOL        Group results by seed (default: True)
#
# ============================================================================
# API CONFIGURATION PARAMETERS
# ============================================================================
#
#   --base-url URL              API base URL (default: https://openrouter.ai/api)
#   --auth-token TOKEN          OpenRouter API key (default: from ANTHROPIC_AUTH_TOKEN env)
#   --model MODEL               Main model (default: anthropic/claude-opus-4.5)
#   --haiku-model MODEL         Fast model (default: anthropic/claude-haiku-4.5)
#
# ============================================================================
# CONTEXT MANAGEMENT PARAMETERS
# ============================================================================
#
#   --clear-tool-uses BOOL      Enable tool use clearing (default: False)
#   --clear-tool-results BOOL   Enable tool result clearing (default: False)
#   --api-max-input-tokens NUM  Max input tokens for API (default: 200000)
#   --api-target-input-tokens NUM Target input tokens for compaction (default: 40000)
#   --disable-prompt-caching BOOL Disable prompt caching (default: False)
#
# ============================================================================
# COMPACTION PARAMETERS (SDK-side context management)
# ============================================================================
#
#   --disable-compact BOOL      Disable SDK compaction (default: False)
#   --autocompact-pct NUM       Autocompact percentage threshold (default: 80)
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
#   ./run_claude_agent_openrouter.sh --config-file final_8k_set_config_multi_seed.json
#
#   # Quick test run with single worker
#   ./run_claude_agent_openrouter.sh --config-file final_8k_set_config_multi_seed.json \
#     --runs-per-config 1 --max-workers 1
#
#   # Run with custom model and background execution
#   ./run_claude_agent_openrouter.sh --config-file final_64k_set_config_multi_seed.json \
#     --model anthropic/claude-sonnet-4 --background
#
#   # Run with context management enabled
#   ./run_claude_agent_openrouter.sh --config-file final_8k_set_config_multi_seed.json \
#     --clear-tool-uses True --autocompact-pct 70
#
#   # Dry run to validate configuration
#   ./run_claude_agent_openrouter.sh --config-file final_8k_set_config_multi_seed.json --dry-run
#
# ============================================================================

set -euo pipefail

# Determine script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ============================================================================
# Default Values
# ============================================================================

# General parameters
STRATEGY="react"
CONFIG_FILE="debug.json"
RUNS_PER_CONFIG="1"
MAX_WORKERS="20"
MAX_TOOL_USES="100"
GROUP_BY_SEED="True"

# API configuration parameters
BASE_URL=""
AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-}"
MODEL="claude-opus-4-5-20251101"
HAIKU_MODEL="claude-haiku-4-5-20251001"

# Context management parameters
CLEAR_TOOL_USES="False"
CLEAR_TOOL_RESULTS="False"
API_MAX_INPUT_TOKENS="200000"
API_TARGET_INPUT_TOKENS="40000"
DISABLE_PROMPT_CACHING="False"

# Compaction parameters
DISABLE_COMPACT="False"
AUTOCOMPACT_PCT="80"

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
        --max-tool-uses)
            MAX_TOOL_USES="$2"
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
        --auth-token)
            AUTH_TOKEN="$2"
            shift 2
            ;;
        --model)
            MODEL="$2"
            shift 2
            ;;
        --haiku-model)
            HAIKU_MODEL="$2"
            shift 2
            ;;
        --clear-tool-uses)
            CLEAR_TOOL_USES="$2"
            shift 2
            ;;
        --clear-tool-results)
            CLEAR_TOOL_RESULTS="$2"
            shift 2
            ;;
        --api-max-input-tokens)
            API_MAX_INPUT_TOKENS="$2"
            shift 2
            ;;
        --api-target-input-tokens)
            API_TARGET_INPUT_TOKENS="$2"
            shift 2
            ;;
        --disable-prompt-caching)
            DISABLE_PROMPT_CACHING="$2"
            shift 2
            ;;
        --disable-compact)
            DISABLE_COMPACT="$2"
            shift 2
            ;;
        --autocompact-pct)
            AUTOCOMPACT_PCT="$2"
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

# Validate API token
if [ -z "$AUTH_TOKEN" ]; then
    echo "Error: API token not provided"
    echo "Please provide API token via --auth-token or set ANTHROPIC_AUTH_TOKEN environment variable"
    exit 1
fi

# Sanitize model name for use in file/directory paths (replace / with -)
MODEL_SAFE="${MODEL//\//-}"

# Determine strategy directory
STRATEGY_DIR="$SCRIPT_DIR/$STRATEGY"

# Check if strategy directory exists
if [ ! -d "$STRATEGY_DIR" ]; then
    echo "Error: Strategy directory not found: $STRATEGY_DIR"
    echo "Please create the directory or use an existing strategy"
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

# ============================================================================
# Setup Environment
# ============================================================================

# Set OpenRouter environment variables
export ANTHROPIC_BASE_URL="$BASE_URL"
export ANTHROPIC_AUTH_TOKEN="$AUTH_TOKEN"
export ANTHROPIC_API_KEY=""  # Must be empty to use OpenRouter instead of Anthropic
export ANTHROPIC_MODEL="$MODEL"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="$HAIKU_MODEL"

# Allow --dangerously-skip-permissions when running as root in container/sandbox
export IS_SANDBOX=1

# Set PYTHONPATH
export PYTHONPATH="$PROJECT_ROOT:${PYTHONPATH:-}"

# Setup directories
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
PARAM_SUFFIX="_MTU${MAX_TOOL_USES}"

# Output directory (permanent storage)
OUTPUT_DIR="$PROJECT_ROOT/evals/benchmarks/${STRATEGY}_${CONFIG_BASENAME}_${MODEL_SAFE}${PARAM_SUFFIX}_${TIMESTAMP}"

# Base task directory inside output directory
BASE_TASK_DIR="$OUTPUT_DIR/tasks"

# Logs directory
LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOGS_DIR"
mkdir -p "$BASE_TASK_DIR"
mkdir -p "$OUTPUT_DIR"

# Log file
LOG_FILE="$LOGS_DIR/claude_agent_${TIMESTAMP}_${CONFIG_FILE}${PARAM_SUFFIX}.log"

# ============================================================================
# Validate Configuration File
# ============================================================================

if [ "$QUIET" != "True" ]; then
    echo "Validating configuration file..."
fi

cd "$PROJECT_ROOT" || exit 1
if ! python "$SCRIPT_DIR/validate_config.py" "$FULL_CONFIG_PATH"; then
    if [ "$QUIET" != "True" ]; then
        echo ""
        echo "⚠ Configuration validation had warnings."
        echo "⚠ This may be due to import checks requiring the gem module."
        echo "⚠ Continuing anyway... (validation will happen again during runtime)"
        echo ""
    fi
fi

# ============================================================================
# Build Command Arguments
# ============================================================================

CMD_ARGS=(
    "--config_file" "$FULL_CONFIG_PATH"
    "--runs_per_config" "$RUNS_PER_CONFIG"
    "--max_workers" "$MAX_WORKERS"
    "--max_tool_uses" "$MAX_TOOL_USES"
    "--group_by_seed" "$GROUP_BY_SEED"
    "--base_task_dir" "$BASE_TASK_DIR"
    "--output_dir" "$OUTPUT_DIR"
    "--use_clear_tool_uses" "$CLEAR_TOOL_USES"
    "--use_clear_tool_results" "$CLEAR_TOOL_RESULTS"
    "--api_max_input_tokens" "$API_MAX_INPUT_TOKENS"
    "--api_target_input_tokens" "$API_TARGET_INPUT_TOKENS"
    "--disable_prompt_caching" "$DISABLE_PROMPT_CACHING"
    "--disable_compact" "$DISABLE_COMPACT"
    "--autocompact_pct" "$AUTOCOMPACT_PCT"
)

# ============================================================================
# Display Configuration
# ============================================================================

if [ "$QUIET" != "True" ]; then
    echo "=================================================================================="
    echo "Claude Agent Parallel Inference (OpenRouter Mode)"
    echo "=================================================================================="
    echo "Strategy:          $STRATEGY"
    echo "Config file:       $FULL_CONFIG_PATH"
    echo "Runs per config:   $RUNS_PER_CONFIG"
    echo "Max workers:       $MAX_WORKERS"
    echo ""
    echo "Model Configuration:"
    echo "  Base URL:        $BASE_URL"
    echo "  Model:           $MODEL"
    echo "  Fast Model:      $HAIKU_MODEL"
    echo "  Max tool uses:   $MAX_TOOL_USES"
    echo "  Group by seed:   $GROUP_BY_SEED"
    echo ""
    echo "Context Management:"
    echo "  Clear tool uses:    $CLEAR_TOOL_USES"
    echo "  Clear tool results: $CLEAR_TOOL_RESULTS"
    echo "  Max input tokens:   $API_MAX_INPUT_TOKENS"
    echo "  Target input tokens: $API_TARGET_INPUT_TOKENS"
    echo "  Prompt caching:     $([ "$DISABLE_PROMPT_CACHING" = "True" ] && echo "Disabled" || echo "Enabled")"
    echo ""
    echo "Compaction Settings:"
    echo "  Disable compact: $DISABLE_COMPACT"
    echo "  Autocompact %:   $AUTOCOMPACT_PCT"
    echo ""
    echo "Directories:"
    echo "  Strategy:        $STRATEGY_DIR"
    echo "  Tasks:           $BASE_TASK_DIR"
    echo "  Output:          $OUTPUT_DIR"
    echo "  Log file:        $LOG_FILE"
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
    echo "cd $PROJECT_ROOT && python $SCRIPT_DIR/run_claude_agent.py ${CMD_ARGS[*]}"
    exit 0
fi

# Change to project root directory
cd "$PROJECT_ROOT" || exit 1

if [ "$QUIET" != "True" ]; then
    echo "PYTHONPATH: $PYTHONPATH"
    echo "Current dir: $(pwd)"
    echo ""
    echo "Running Claude Agent parallel inference..."
    echo ""
fi

# Build Python command
PYTHON_CMD="python $SCRIPT_DIR/run_claude_agent.py ${CMD_ARGS[*]}"

if [ "$BACKGROUND" = "True" ]; then
    # Background execution with nohup
    nohup $PYTHON_CMD > "$LOG_FILE" 2>&1 &
    PID=$!

    # Save PID
    PID_FILE="$LOGS_DIR/${STRATEGY}_${CONFIG_BASENAME}_${TIMESTAMP}.pid"
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
echo "=================================================================================="
echo "✓ Inference completed successfully!"
echo "Results saved to: $OUTPUT_DIR"
echo "=================================================================================="
