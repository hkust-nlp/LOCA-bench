#!/bin/bash

# Remote Parallel Inference Runner Script with Docker Backend
#
# This script runs inference with remote Docker-based environments.
# The LLM API calls happen locally, while tool execution happens in Docker containers.
#
# Usage:
#   ./run_remote.sh --config-file CONFIG.json [OPTIONS]
#
# See run.sh for detailed parameter documentation.
# This script accepts all the same parameters as run.sh, plus:
#
# ============================================================================
# REMOTE-SPECIFIC PARAMETERS
# ============================================================================
#
#   --execution-mode MODE       Execution mode (default: sandbox)
#                               Options:
#                                 - local: Server runs as local Python process (for debugging)
#                                 - sandbox: Server runs in container (for isolation)
#   --container-runtime RUNTIME Container runtime to use (default: docker)
#                               Options: docker, podman
#   --docker-image IMAGE        Container image to use for sandbox mode (default: loca-bench:latest)
#   --base-port NUM             Base port for servers (default: 9000)
#                               Each server uses base-port + run_id
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
CONFIG_FILE="final_8k_set_config_multi_seed.json"
RUNS_PER_CONFIG="1"
MAX_WORKERS="20"
API_KEY=""
BASE_URL=""
MODEL="deepseek-reasoner"
MAX_TOKENS="32768"
MAX_CONTEXT_SIZE="128000"
GROUP_BY_SEED="True"
RESUME=""

# Remote-specific parameters
EXECUTION_MODE="sandbox"
DOCKER_IMAGE="loca-bench:latest"
CONTAINER_RUNTIME="docker"
BASE_PORT="9000"

# Context Editing parameters
CONTEXT_RESET="False"
RESET_SIZE="200000"
RESET_RATIO="0.5"
THINKING_RESET="False"
KEEP_THINKING="1"

# Context Compaction parameters
CONTEXT_SUMMARY="False"

# Context Awareness parameters
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
        --execution-mode)
            EXECUTION_MODE="$2"
            shift 2
            ;;
        --docker-image)
            DOCKER_IMAGE="$2"
            shift 2
            ;;
        --container-runtime)
            CONTAINER_RUNTIME="$2"
            shift 2
            ;;
        --base-port)
            BASE_PORT="$2"
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
    echo "Usage: ./run_remote.sh --config-file CONFIG.json [OPTIONS]"
    exit 1
fi

# Validate strategy parameter
if [[ "$STRATEGY" != "react" && "$STRATEGY" != "ptc" && "$STRATEGY" != "memory_tool" ]]; then
    echo "Error: Invalid strategy '$STRATEGY'"
    echo "Valid strategies: react, ptc, memory_tool"
    exit 1
fi

# Validate execution mode parameter
if [[ "$EXECUTION_MODE" != "local" && "$EXECUTION_MODE" != "sandbox" ]]; then
    echo "Error: Invalid execution mode '$EXECUTION_MODE'"
    echo "Valid execution modes: local, sandbox"
    exit 1
fi

# Validate container runtime parameter
if [[ "$CONTAINER_RUNTIME" != "docker" && "$CONTAINER_RUNTIME" != "podman" ]]; then
    echo "Error: Invalid container runtime '$CONTAINER_RUNTIME'"
    echo "Valid container runtimes: docker, podman"
    exit 1
fi

# Only check container runtime if in sandbox mode
if [[ "$EXECUTION_MODE" == "sandbox" ]]; then
    # Check if container runtime is installed and running
    if ! command -v "$CONTAINER_RUNTIME" &> /dev/null; then
        echo "Error: $CONTAINER_RUNTIME is not installed"
        if [[ "$CONTAINER_RUNTIME" == "docker" ]]; then
            echo "Please install Docker from https://docs.docker.com/get-docker/"
        else
            echo "Please install Podman from https://podman.io/getting-started/installation"
        fi
        exit 1
    fi

    if ! "$CONTAINER_RUNTIME" info &> /dev/null; then
        echo "Error: $CONTAINER_RUNTIME daemon/service is not running"
        echo "Please start $CONTAINER_RUNTIME and try again"
        exit 1
    fi

    # Build container image if it doesn't exist
    if [ -z "$($CONTAINER_RUNTIME images -q $DOCKER_IMAGE 2> /dev/null)" ]; then
        echo "=================================================================================="
        echo "Building container image with $CONTAINER_RUNTIME..."
        echo "=================================================================================="
        cd "$PROJECT_ROOT" || exit 1
        "$CONTAINER_RUNTIME" build -t "$DOCKER_IMAGE" .
        if [ $? -ne 0 ]; then
            echo "Error: Failed to build container image"
            exit 1
        fi
        echo "Container image built successfully!"
        echo ""
    fi
fi

# Sanitize model name for use in file/directory paths
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
    FULL_CONFIG_PATH="$CONFIG_FILE"
else
    FULL_CONFIG_PATH="$STRATEGY_DIR/$CONFIG_FILE"
fi

# Check if config file exists
if [ ! -f "$FULL_CONFIG_PATH" ]; then
    echo "Error: Config file not found: $FULL_CONFIG_PATH"
    echo "Available configs in $STRATEGY_DIR:"
    ls -1 "$STRATEGY_DIR"/*.json 2>/dev/null || echo "  No JSON files found"
    exit 1
fi

# Extract config file basename
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

# Add execution mode indicator
if [[ "$EXECUTION_MODE" == "sandbox" ]]; then
    PARAM_SUFFIX="${PARAM_SUFFIX}_SANDBOX"
else
    PARAM_SUFFIX="${PARAM_SUFFIX}_LOCAL"
fi

# Setup directories with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Handle resume mode
if [ -n "$RESUME" ]; then
    if [ "$RESUME" = "true" ]; then
        OUTPUT_DIR="$PROJECT_ROOT/outputs/inf_${STRATEGY}_${CONFIG_BASENAME}_${MODEL_SAFE}${PARAM_SUFFIX}"
    else
        OUTPUT_DIR="$RESUME"
    fi

    if [ ! -d "$OUTPUT_DIR" ]; then
        echo "Error: Resume directory does not exist: $OUTPUT_DIR"
        exit 1
    fi

    echo "RESUME MODE: Using existing output directory: $OUTPUT_DIR"
else
    OUTPUT_DIR="$PROJECT_ROOT/outputs/inf_${STRATEGY}_${CONFIG_BASENAME}_${MODEL_SAFE}${PARAM_SUFFIX}_${TIMESTAMP}"
fi

# Base task directory inside output directory
# Put task workspaces directly under output dir (not in tasks/ subdirectory)
BASE_TASK_DIR="$OUTPUT_DIR"

mkdir -p "$BASE_TASK_DIR"
mkdir -p "$OUTPUT_DIR"

# Set environment variables
export PYTHONPATH="$PROJECT_ROOT:$PROJECT_ROOT/mcp-convert:$PYTHONPATH"

# Change to project root for execution
cd "$PROJECT_ROOT" || exit 1

# Print configuration
echo "=================================================================================="
if [ -n "$RESUME" ]; then
    echo "Starting Remote Parallel Inference (RESUME MODE)"
else
    echo "Starting Remote Parallel Inference"
fi
echo "=================================================================================="
echo "Strategy:          $STRATEGY"
echo "Config file:       $FULL_CONFIG_PATH"
echo "Runs per config:   $RUNS_PER_CONFIG"
echo "Max workers:       $MAX_WORKERS"
echo ""
echo "Remote Configuration:"
echo "  Execution mode:  $EXECUTION_MODE"
if [[ "$EXECUTION_MODE" == "sandbox" ]]; then
echo "  Container runtime: $CONTAINER_RUNTIME"
echo "  Container image: $DOCKER_IMAGE"
fi
echo "  Base port:       $BASE_PORT"
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

# Run the remote inference
python "$SCRIPT_DIR/run_react_remote.py" \
    --config_file "$FULL_CONFIG_PATH" \
    --runs_per_config "$RUNS_PER_CONFIG" \
    --max_workers "$MAX_WORKERS" \
    --api_key "$API_KEY" \
    --base_url "$BASE_URL" \
    --model "$MODEL" \
    --base_task_dir "$BASE_TASK_DIR" \
    --output_dir "$OUTPUT_DIR" \
    --execution_mode "$EXECUTION_MODE" \
    --docker_image "$DOCKER_IMAGE" \
    --container_runtime "$CONTAINER_RUNTIME" \
    --base_port "$BASE_PORT" \
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
echo "Remote inference completed!"
echo "Results saved to: $OUTPUT_DIR"
echo "=================================================================================="
