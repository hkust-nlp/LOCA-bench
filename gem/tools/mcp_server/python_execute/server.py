#!/usr/bin/env python3
"""
Python Execute MCP Server

An MCP server that provides Python code execution capabilities in an isolated environment.
Based on mcpbench_dev/utils/aux_tools/python_interpretor.py
"""

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Annotated, Optional

# Add parent directory to path for imports
gem_root = Path(__file__).parent.parent.parent.parent.parent
if str(gem_root) not in sys.path:
    sys.path.insert(0, str(gem_root))

from fastmcp import FastMCP

# Create FastMCP server
app = FastMCP("Python Execute Server")

# Default workspace (can be overridden by environment variable)
DEFAULT_WORKSPACE = "."


def get_workspace() -> str:
    """Get the workspace directory from environment or use default."""
    return os.environ.get("PYTHON_EXECUTE_WORKSPACE", DEFAULT_WORKSPACE)


@app.tool()
def python_execute(
    code: Annotated[str, "Python code to execute (can be directly pasted into a .py file)"],
    filename: Annotated[Optional[str], "Filename for the Python file (including .py extension). If not provided, a random UUID will be used."] = None,
    timeout: Annotated[Optional[int], "Maximum execution time in seconds. Cannot exceed 120 seconds. If a value greater than 120 is provided, it will be automatically limited to 120 seconds. Default is 30 seconds."] = 30
) -> str:
    """Execute Python code directly under the agent workspace, and returns stdout, stderr, return code, and execution time in a structured format."""
    try:
        # 使用提供的 filename 或生成随机 UUID
        if filename is None:
            filename = f"{uuid.uuid4()}.py"
        
        # 确保 timeout 不超过 120 秒
        if timeout is None:
            timeout = 30
        if timeout > 120:
            timeout = 120
        
        # 确保文件名以 .py 结尾
        if not filename.endswith(".py"):
            filename += ".py"
        
        # 获取工作目录
        agent_workspace = get_workspace()
        agent_workspace = os.path.abspath(agent_workspace)
        
        # 创建 .python_tmp 目录
        tmp_dir = os.path.join(agent_workspace, '.python_tmp')
        os.makedirs(tmp_dir, exist_ok=True)
        
        # 创建 Python 文件
        file_path = os.path.join(tmp_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(code)
        
        # 记录开始时间
        start_time = time.time()
        
        # 执行 Python 文件
        cmd = f"uv run --directory {agent_workspace} ./.python_tmp/{filename}"
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=timeout
            )
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            return f"=== EXECUTION TIMEOUT ===\nExecution timed out after {timeout} seconds\nExecution time: {execution_time:.3f} seconds"
        
        # 计算执行时间
        execution_time = time.time() - start_time
        
        # 构建输出
        output_parts = []
        
        # 添加标准输出
        if result.stdout:
            output_parts.append("=== STDOUT ===")
            output_parts.append(result.stdout.rstrip())
        
        # 添加标准错误
        if result.stderr:
            output_parts.append("=== STDERR ===")
            output_parts.append(result.stderr.rstrip())
        
        # 添加执行信息
        output_parts.append("=== EXECUTION INFO ===")
        output_parts.append(f"Return code: {result.returncode}")
        output_parts.append(f"Execution time: {execution_time:.3f} seconds")
        output_parts.append(f"Timeout limit: {timeout} seconds")
        
        # 如果没有任何输出
        if not result.stdout and not result.stderr:
            output_parts.insert(0, "No console output produced.")
        
        return "\n".join(output_parts)
        
    except Exception as e:
        return f"Error executing Python code: {str(e)}"


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Python Execute MCP Server")
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
        default=8084,
        help="Port to bind to (for HTTP transport)"
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Agent workspace directory (default: current directory)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    # Set workspace environment variable
    os.environ["PYTHON_EXECUTE_WORKSPACE"] = os.path.abspath(args.workspace)
    
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

