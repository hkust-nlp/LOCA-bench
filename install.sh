#!/usr/bin/env bash
set -euo pipefail

# ====== Config ======
# Determine paths relative to this script's location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GEM_DIR="${SCRIPT_DIR}"
PROJECT_ROOT="$(dirname "${GEM_DIR}")"

# Node config (match your Dockerfile)
NVM_VERSION="${NVM_VERSION:-v0.40.3}"
NODE_MAJOR="${NODE_MAJOR:-24}"
NODE_BIN_VERSION="${NODE_BIN_VERSION:-v24.12.0}"  # used for symlinks like Dockerfile

export DEBIAN_FRONTEND=noninteractive

# ====== Helpers ======
log() { echo -e "\n[install] $*\n"; }

# ====== 1) Python deps ======
log "Installing Python dependencies (pip)..."
python -m pip install --upgrade pip

# Your original pip installs
python -m pip install \
  fire \
  python-dotenv \
  fastmcp \
  tiktoken \
  uv \
  excel-mcp-server \
  reportlab

# Pre-install common deps MCP servers need
python -m pip install --no-cache-dir \
  cryptography \
  ruff \
  black \
  pandas \
  numpy \
  pydantic-core \
  openpyxl \
  pillow

# Install your local project in editable mode
if [[ -d "$GEM_DIR" ]]; then
  log "Installing local project editable: $GEM_DIR"
  (cd "$GEM_DIR" && python -m pip install -e .)
else
  log "WARNING: GEM_DIR not found: $GEM_DIR (skip pip install -e .)"
fi

# ====== 2) nvm + Node ======
log "Installing nvm ($NVM_VERSION) and Node.js ($NODE_MAJOR)..."
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"

if [[ ! -s "$NVM_DIR/nvm.sh" ]]; then
  curl -fsSL "https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh" | bash
fi

# shellcheck source=/dev/null
. "$NVM_DIR/nvm.sh"

nvm install "$NODE_MAJOR"
nvm use "$NODE_MAJOR"
nvm alias default "$NODE_MAJOR"

# ====== 3) Create symlinks like Dockerfile ======
log "Creating local bin symlinks for node/npm/npx..."
mkdir -p "$HOME/.local/bin"

NODE_DIR="$NVM_DIR/versions/node/$NODE_BIN_VERSION/bin"
if [[ -d "$NODE_DIR" ]]; then
  ln -sf "$NODE_DIR/node" "$HOME/.local/bin/node"
  ln -sf "$NODE_DIR/npm"  "$HOME/.local/bin/npm"
  ln -sf "$NODE_DIR/npx"  "$HOME/.local/bin/npx"
else
  log "WARNING: Expected Node dir not found: $NODE_DIR"
  log "         Your actual Node version path is:"
  which node || true
fi

export PATH="$HOME/.local/bin:$NVM_DIR/versions/node/$NODE_BIN_VERSION/bin:$PATH"

# ====== 4) npm global packages ======
log "Installing npm global packages..."
npm install -g @modelcontextprotocol/server-filesystem @modelcontextprotocol/server-memory

# ====== 5) Pre-cache uvx tools ======
log "Pre-caching uvx tools (ignore failures)..."
uvx --help || true
uvx cli-mcp-server --help || true
uvx pdf-tools-mcp --help || true

log "Done ✅"
