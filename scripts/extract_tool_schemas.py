#!/usr/bin/env python3
"""
Extract tool schemas from all MCP servers in LOCA-bench.

This script launches each MCP server, discovers available tools, and saves
their schemas to a JSON file for easy review.

Usage:
    python scripts/extract_tool_schemas.py [--config CONFIG_FILE] [--output OUTPUT_FILE]

Example:
    python scripts/extract_tool_schemas.py
    python scripts/extract_tool_schemas.py --output my_tools.json
    python scripts/extract_tool_schemas.py --servers canvas,email,google_cloud
"""

import argparse
import json
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "mcp_convert"))

from gem.tools.mcp_server.config_loader import build_server_config
from gem.tools.mcp_tool import MCPTool


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load the MCP servers configuration file."""
    with open(config_path, "r") as f:
        return json.load(f)


def replace_placeholders(value: Any, replacements: Dict[str, str]) -> Any:
    """Recursively replace placeholders in config values."""
    if isinstance(value, str):
        for placeholder, replacement in replacements.items():
            value = value.replace(f"{{{placeholder}}}", replacement)
        return value
    elif isinstance(value, dict):
        return {k: replace_placeholders(v, replacements) for k, v in value.items()}
    elif isinstance(value, list):
        return [replace_placeholders(item, replacements) for item in value]
    return value


def setup_temp_directories(config: Dict[str, Any], temp_base: Path) -> None:
    """Create temporary directories for servers that need data directories."""
    servers = config.get("servers", {})
    for server_name, server_config in servers.items():
        if not server_config.get("enabled", True):
            continue
        params = server_config.get("params", {})
        for key, value in params.items():
            if isinstance(value, str) and ("_dir" in key or "path" in key.lower() or "directory" in key.lower()):
                # Create the directory
                dir_path = Path(value)
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"  Created directory: {dir_path}")


def extract_tools_from_server(
    server_name: str,
    server_type: str,
    params: Dict[str, Any],
    timeout: float = 30.0
) -> Dict[str, Any]:
    """Extract tool schemas from a single MCP server."""
    result = {
        "server_name": server_name,
        "server_type": server_type,
        "status": "pending",
        "tools": [],
        "error": None
    }

    try:
        # Build stdio config using the config loader
        stdio_config = build_server_config(
            server_type=server_type,
            params=params,
            server_name=server_name
        )

        # Create MCP config
        mcp_config = {"mcpServers": stdio_config}

        print(f"  Connecting to {server_name} ({server_type})...")

        # Create MCPTool and discover tools
        tool = MCPTool(
            config=mcp_config,
            validate_on_init=True,
            execution_timeout=timeout,
            max_retries=2
        )

        # Get available tools
        tools = tool.get_available_tools()

        # Format tools for output
        formatted_tools = []
        for t in tools:
            formatted_tool = {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters", {"type": "object", "properties": {}})
            }
            formatted_tools.append(formatted_tool)

        result["tools"] = formatted_tools
        result["status"] = "success"
        result["tool_count"] = len(formatted_tools)

        # Clean up
        tool.close()

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"  Error: {e}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Extract tool schemas from MCP servers")
    parser.add_argument(
        "--config",
        type=str,
        default=str(PROJECT_ROOT / "scripts" / "all_mcp_servers_config.json"),
        help="Path to the MCP servers configuration file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(PROJECT_ROOT / "scripts" / "mcp_tool_schemas.json"),
        help="Path to output JSON file"
    )
    parser.add_argument(
        "--servers",
        type=str,
        default=None,
        help="Comma-separated list of servers to extract (default: all enabled servers)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout in seconds for each server connection"
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary data directories after extraction"
    )
    args = parser.parse_args()

    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)

    print(f"Loading configuration from: {config_path}")
    config = load_config(config_path)

    # Set up temp data directory
    temp_data_dir = PROJECT_ROOT / config.get("temp_data_dir", "./temp_mcp_data")
    temp_data_dir = temp_data_dir.resolve()

    # Replace placeholders in config
    replacements = {"temp_data_dir": str(temp_data_dir)}
    config = replace_placeholders(config, replacements)

    print(f"Temporary data directory: {temp_data_dir}")

    # Create temp directories
    print("\nSetting up temporary directories...")
    setup_temp_directories(config, temp_data_dir)

    # Determine which servers to process
    servers = config.get("servers", {})
    if args.servers:
        selected_servers = [s.strip() for s in args.servers.split(",")]
        servers = {k: v for k, v in servers.items() if k in selected_servers}

    # Extract tools from each server
    results = {
        "metadata": {
            "extracted_at": datetime.now().isoformat(),
            "project_root": str(PROJECT_ROOT),
            "config_file": str(config_path),
            "total_servers": len(servers)
        },
        "servers": {},
        "all_tools": []
    }

    print(f"\nExtracting tools from {len(servers)} servers...\n")

    successful = 0
    failed = 0

    for server_name, server_config in servers.items():
        if not server_config.get("enabled", True):
            print(f"[SKIP] {server_name} (disabled)")
            continue

        print(f"[{server_name}]")
        server_type = server_config.get("type", server_name)
        params = server_config.get("params", {})

        result = extract_tools_from_server(
            server_name=server_name,
            server_type=server_type,
            params=params,
            timeout=args.timeout
        )

        results["servers"][server_name] = result

        if result["status"] == "success":
            successful += 1
            print(f"  ✓ Found {result['tool_count']} tools")

            # Add to all_tools with server info
            for tool in result["tools"]:
                tool_with_server = tool.copy()
                tool_with_server["_server"] = server_name
                results["all_tools"].append(tool_with_server)
        else:
            failed += 1
            print(f"  ✗ Failed")

        print()

    # Update metadata
    results["metadata"]["successful_servers"] = successful
    results["metadata"]["failed_servers"] = failed
    results["metadata"]["total_tools"] = len(results["all_tools"])

    # Sort all_tools by name
    results["all_tools"].sort(key=lambda t: t["name"])

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"{'='*50}")
    print(f"Summary:")
    print(f"  Successful: {successful}/{len(servers)} servers")
    print(f"  Failed: {failed}/{len(servers)} servers")
    print(f"  Total tools: {len(results['all_tools'])}")
    print(f"\nResults saved to: {output_path}")

    # Clean up temp directories unless --keep-temp is specified
    if not args.keep_temp and temp_data_dir.exists():
        print(f"\nCleaning up temporary directories...")
        shutil.rmtree(temp_data_dir)
        print(f"  Removed: {temp_data_dir}")

    # Print tool summary grouped by server
    print(f"\n{'='*50}")
    print("Tool Summary by Server:")
    print(f"{'='*50}")

    for server_name, server_result in results["servers"].items():
        if server_result["status"] == "success":
            print(f"\n[{server_name}] ({server_result['tool_count']} tools)")
            for tool in server_result["tools"]:
                desc = tool["description"][:60] + "..." if len(tool.get("description", "")) > 60 else tool.get("description", "")
                print(f"  - {tool['name']}: {desc}")


if __name__ == "__main__":
    main()
