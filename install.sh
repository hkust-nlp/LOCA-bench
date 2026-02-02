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

# Create symlinks
ln -sf "$NODE_DIR/node" "$HOME/.local/bin/node"
ln -sf "$NODE_DIR/npm"  "$HOME/.local/bin/npm"
ln -sf "$NODE_DIR/npx"  "$HOME/.local/bin/npx"

# Update PATH for this session
export PATH="$HOME/.local/bin:$PATH"

# ====== 4) npm global packages ======
log "Installing npm global packages..."
npm install -g @modelcontextprotocol/server-filesystem @modelcontextprotocol/server-memory

# ====== 5) Pre-cache uvx tools ======
log "Pre-caching uvx tools (ignore failures)..."
uvx --help || true
uv tool install cli-mcp-server  || true
uv tool install pdf-tools-mcp  || true

log "Done ✅"
