#!/usr/bin/env python3
"""
Claim Done MCP Server

A simple MCP server that provides a claim_done tool for agents to signal task completion.
Based on mcpbench_dev/utils/aux_tools/basic.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
gem_root = Path(__file__).parent.parent.parent.parent.parent
if str(gem_root) not in sys.path:
    sys.path.insert(0, str(gem_root))

from fastmcp import FastMCP

# Create FastMCP server
app = FastMCP("Claim Done Server")


@app.tool()
def claim_done() -> str:
    """claim the task is done"""
    return "you have claimed the task is done!"


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Claim Done MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="Transport type (default: stdio)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (for HTTP transport)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8083,
        help="Port to bind to (for HTTP transport)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Run the server
    if args.transport == "stdio":
        app.run(transport="stdio")
    else:
        app.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            log_level=args.log_level
        )

