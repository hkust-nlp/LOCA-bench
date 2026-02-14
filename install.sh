#!/bin/bash
set -euo pipefail

# ====== Config ======
# Determine paths relative to this script's location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}"
PROJECT_ROOT="${PROJECT_DIR}"

# Node config
NVM_VERSION="${NVM_VERSION:-v0.40.3}"
NODE_MAJOR="${NODE_MAJOR:-24}"

export DEBIAN_FRONTEND=noninteractive

# ====== Helpers ======
log() { echo -e "\n[install] $*\n"; }

# ====== 1) Python deps ======
log "Installing Python dependencies..."
python -m pip install --upgrade pip

# Install the project with all dependencies in editable mode
if [[ -d "$PROJECT_DIR" ]]; then
  log "Installing LOCA-bench with all dependencies (editable mode)..."
  (cd "$PROJECT_DIR" && python -m pip install -e ".")
else
  log "WARNING: Project directory not found: $PROJECT_DIR"
  exit 1
fi

# ====== 2) nvm + Node ======
log "Installing nvm ($NVM_VERSION) and Node.js ($NODE_MAJOR)..."
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

# Install nvm if not already installed
if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
  log "Installing nvm..."
  curl -fsSL "https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh" | bash

  if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
    log "ERROR: nvm installation failed"
    exit 1
  fi
fi

# Load nvm
# shellcheck source=/dev/null
. "$NVM_DIR/nvm.sh"

# Install and configure Node.js
log "Installing Node.js v$NODE_MAJOR..."
nvm install "$NODE_MAJOR"
nvm use "$NODE_MAJOR"
nvm alias default "$NODE_MAJOR"

# Verify installation
if ! command -v node &> /dev/null; then
  log "ERROR: Node.js installation failed"
  exit 1
fi

# ====== 3) Create symlinks for easier access ======
log "Creating symlinks for node/npm/npx in ~/.local/bin..."
mkdir -p "$HOME/.local/bin"

# Dynamically get the actual installed node path
NODE_PATH="$(nvm which node)"
if [[ -z "$NODE_PATH" ]]; then
  log "ERROR: Could not determine node path"
  exit 1
fi

NODE_DIR="$(dirname "$NODE_PATH")"
log "Node.js installed at: $NODE_DIR"

# Create symlinks for core binaries
ln -sf "$NODE_DIR/node" "$HOME/.local/bin/node"
ln -sf "$NODE_DIR/npm"  "$HOME/.local/bin/npm"
ln -sf "$NODE_DIR/npx"  "$HOME/.local/bin/npx"

# Update PATH for this session
export PATH="$HOME/.local/bin:$PATH"

# ====== 4) npm global packages ======
log "Installing npm global packages..."
npm install -g @modelcontextprotocol/server-filesystem @modelcontextprotocol/server-memory

# Symlink ALL binaries from the nvm bin dir to ~/.local/bin
# This ensures globally installed npm package binaries (e.g. mcp-server-*)
# are available on PATH at runtime, even when NVM_DIR is not set.
log "Symlinking all nvm bin entries to ~/.local/bin..."
for bin_file in "$NODE_DIR"/*; do
  bin_name="$(basename "$bin_file")"
  # Don't overwrite existing symlinks (node, npm, npx already done)
  if [[ ! -e "$HOME/.local/bin/$bin_name" ]]; then
    ln -sf "$bin_file" "$HOME/.local/bin/$bin_name"
    log "  Linked: $bin_name"
  fi
done

# ====== 5) Install uv tools (cli-mcp-server, pdf-tools-mcp) ======
# Must happen BEFORE verification so the direct binaries are available.
log "Installing uv tools..."
uv tool install cli-mcp-server
uv tool install pdf-tools-mcp

# ====== 6) Verify MCP servers can start ======
# Test that the direct binaries work with a stripped env (like MCP SDK does at runtime).
log "Verifying MCP server binaries start correctly..."

_VERIFY_PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
_INIT_MSG='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}'

for server_info in \
  "filesystem:mcp-server-filesystem /tmp" \
  "memory:mcp-server-memory" \
  "terminal:env ALLOWED_DIR=/tmp cli-mcp-server" \
  "pdf_tools:pdf-tools-mcp"; do

  srv_name="${server_info%%:*}"
  srv_cmd="${server_info#*:}"

  log "  Testing $srv_name: $srv_cmd"

  # Send MCP initialize request and check for a JSON response.
  set +e
  response=$(echo "$_INIT_MSG" | env -i HOME="$HOME" PATH="$_VERIFY_PATH" \
    timeout 10 $srv_cmd 2>/dev/null)
  rc=$?
  set -e

  if echo "$response" | grep -q '"protocolVersion"'; then
    log "  ✅ $srv_name: responded to MCP initialize"
  else
    log "  ❌ $srv_name: no valid MCP response (exit code $rc)"
    log "  Response: $response"
    exit 1
  fi
done

log "Done ✅"
