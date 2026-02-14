FROM python:3.10-slim

# Install system dependencies required for LOCA-bench
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    build-essential \
    sqlite3 \
    libsqlite3-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# nvm dir for install.sh (which installs nvm + Node 24 + npm packages)
ENV NVM_DIR=/root/.nvm

# install.sh creates ~/.local/bin symlinks to the nvm-installed Node.
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Use install.sh to set up the environment
# This ensures consistency between local and server environments
RUN chmod +x install.sh && \
    bash install.sh

# Set environment variables for sandbox execution
ENV PYTHONPATH="${PYTHONPATH}:/app:/app/mcp_convert"
ENV PYTHONUNBUFFERED=1

# Create directories for runtime data
RUN mkdir -p /app/outputs /app/logs

# Expose server port for HTTP API
EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Default command: start the HTTP server
# Can be overridden for different modes (e.g., running specific tasks)
CMD ["python", "gem/server/http_server.py", "--host", "0.0.0.0", "--port", "8000"]
