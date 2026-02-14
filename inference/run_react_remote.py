# Copyright 2025 AxonRL Team. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Flexible parallel inference runner with remote environment via Docker."""

import json
import os
import sys
import time
import subprocess
import importlib
import socket
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

import fire
import requests
from dotenv import load_dotenv
import random
from requests.exceptions import RequestException, HTTPError

# Import remote environment client
from gem.client.remote_env_client import RemoteEnvironmentClient

load_dotenv()

logger = logging.getLogger(__name__)


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """Check if a port is available for binding.

    Tests both the requested host and localhost (if binding to all interfaces)
    to catch conflicts with localhost-only listeners.

    Args:
        port: Port number to check
        host: Host address to check

    Returns:
        True if port is available, False otherwise
    """
    # Test the requested host (without SO_REUSEADDR to detect actual conflicts)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
    except OSError:
        return False

    # Also test localhost if binding to all interfaces
    if host == "0.0.0.0":
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
        except OSError:
            return False

    return True


def find_available_port(base_port: int, max_attempts: int = 100) -> int:
    """Find an available port starting from base_port.

    Args:
        base_port: Starting port number
        max_attempts: Maximum number of ports to try

    Returns:
        Available port number

    Raises:
        RuntimeError: If no available port found
    """
    for offset in range(max_attempts):
        port = base_port + offset
        if is_port_available(port):
            return port

    raise RuntimeError(f"Could not find available port after trying {max_attempts} ports starting from {base_port}")


def dynamic_import_class(class_path: str):
    """Dynamically import a class from a module path.

    Args:
        class_path: Full path to class, e.g., 'gem.envs.canvas_list_test_s2l.canvas_list_test_s2l.CanvasListTestS2LEnv'

    Returns:
        The imported class
    """
    module_path, class_name = class_path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def start_docker_container(config_name: str, task_id: int, run_id: int, base_port: int, task_workspace: Path, docker_image: str = "loca-bench:latest", container_runtime: str = "docker", log_file: Optional[Path] = None) -> tuple:
    """Start a container for the remote environment.

    Args:
        config_name: Configuration/task name
        task_id: Globally unique task ID (used for port assignment)
        run_id: Run number (used for container naming)
        base_port: Base port number to use
        task_workspace: Path to task workspace to mount
        docker_image: Container image to use (default: "loca-bench:latest")
        container_runtime: Container runtime to use - "docker" or "podman" (default: "docker")
        log_file: Optional path to redirect container logs for real-time viewing

    Returns:
        Tuple of (container_name, port, process, log_file_handle)
        - container_name: Name of the container
        - port: Port number the server is listening on
        - process: subprocess.Popen object (for non-detached mode)
        - log_file_handle: File handle for the log file (or None)
    """
    container_name = f"loca-task-{config_name}-{run_id}"

    # Find an available port starting from base_port + task_id
    preferred_port = base_port + task_id
    host_port = find_available_port(preferred_port, max_attempts=100)

    if host_port != preferred_port:
        logger.warning(f"Preferred port {preferred_port} not available for Docker, using {host_port} instead")

    # Ensure task workspace parent exists (we mount the parent to allow env to delete/recreate task_workspace)
    task_workspace.parent.mkdir(parents=True, exist_ok=True)

    # Build container run command
    # Mount the PARENT directory so the environment can delete/recreate the task_workspace subdirectory
    # (Cannot rmtree a mount point itself - "Device or resource busy")
    # Note: We don't use -d (detached) mode so we can capture logs in real-time
    container_cmd = [
        container_runtime, "run",
        "--rm",  # Auto-remove container when it exits
        "--name", container_name,
        "-p", f"{host_port}:8000",
        "-v", f"{task_workspace.parent}:/workspace/outputs/tasks/{config_name}",
        docker_image
    ]

    logger.info(f"Starting {container_runtime} container: {container_name} on port {host_port}")
    logger.debug(f"Container command: {' '.join(container_cmd)}")

    try:
        log_file_handle = None
        if log_file:
            # Create directory if it doesn't exist
            log_file.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Container logs will be written to: {log_file}")

            # Open log file for writing with line buffering
            log_file_handle = open(log_file, 'w', buffering=1)  # Line buffered
            log_file_handle.write(f"=== Container Log Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            log_file_handle.write(f"=== Container: {container_name} | Image: {docker_image} | Port: {host_port} ===\n")
            log_file_handle.flush()

            # Start container with stdout/stderr redirected to file (real-time logging)
            process = subprocess.Popen(
                container_cmd,
                stdout=log_file_handle,
                stderr=subprocess.STDOUT,
                cwd=str(task_workspace.parent)
            )
        else:
            # No log file - run with stdout/stderr going to devnull
            process = subprocess.Popen(
                container_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(task_workspace.parent)
            )

        logger.info(f"Container started: {container_name} (PID {process.pid})")
        return container_name, host_port, process, log_file_handle
    except Exception as e:
        logger.error(f"Failed to start {container_runtime} container: {e}")
        if log_file_handle:
            log_file_handle.close()
        raise RuntimeError(f"Failed to start {container_runtime} container: {e}") from e


def stop_docker_container(container_name: str, container_runtime: str = "docker", process: Optional[subprocess.Popen] = None, log_file_handle=None):
    """Stop and remove a container.

    Args:
        container_name: Name of the container to stop
        container_runtime: Container runtime to use - "docker" or "podman" (default: "docker")
        process: Optional Popen process (for non-detached mode)
        log_file_handle: Optional log file handle to close
    """
    logger.info(f"Stopping {container_runtime} container: {container_name}")

    try:
        # Stop the container (this will cause the Popen process to exit if running non-detached)
        subprocess.run([container_runtime, "stop", container_name], capture_output=True, text=True, check=False)

        # Wait for process to exit if we have one
        if process and process.poll() is None:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

        # Try to remove container (may already be removed if --rm was used)
        subprocess.run([container_runtime, "rm", container_name], capture_output=True, text=True, check=False)

        logger.info(f"Container stopped and removed: {container_name}")
    except Exception as e:
        logger.warning(f"Error while stopping {container_runtime} container {container_name}: {e}")
    finally:
        # Close log file handle if provided
        if log_file_handle:
            try:
                log_file_handle.flush()
                log_file_handle.close()
            except Exception as e:
                logger.warning(f"Failed to close log file handle: {e}")


def wait_for_server_health(port: int, server_process: Optional[subprocess.Popen] = None, max_retries: int = 30, retry_interval: float = 1.0) -> bool:
    """Wait for server to become healthy.

    Args:
        port: Port to check
        server_process: Optional server process (for local mode debugging)
        max_retries: Maximum number of retry attempts
        retry_interval: Time to wait between retries in seconds

    Returns:
        True if server is healthy, False otherwise
    """
    server_url = f"http://localhost:{port}"

    for attempt in range(max_retries):
        # Check if process has died (local mode only)
        if server_process and server_process.poll() is not None:
            logger.error(f"Server process died with exit code {server_process.returncode}")

            # Try to get output from the process
            try:
                stdout, stderr = server_process.communicate(timeout=1)
                if stdout:
                    logger.error(f"Server stdout:\n{stdout}")
                if stderr:
                    logger.error(f"Server stderr:\n{stderr}")
            except:
                pass

            return False

        try:
            response = requests.get(f"{server_url}/api/v1/health", timeout=5)
            if response.status_code == 200:
                logger.info(f"Server at port {port} is healthy")
                return True
        except requests.exceptions.RequestException as e:
            if attempt == 0:
                logger.debug(f"Waiting for server to start on port {port}...")

        if attempt < max_retries - 1:
            time.sleep(retry_interval)

    # Health check failed - try to get diagnostic info
    logger.error(f"Server at port {port} did not become healthy after {max_retries} attempts")

    if server_process:
        if server_process.poll() is None:
            # Process is still running
            logger.error("Server process is running but not responding to health checks")
            logger.error("Attempting to get server output...")
            try:
                # Give it a moment to output something
                time.sleep(1)
                # Try to read any available output (non-blocking)
                import select
                if hasattr(select, 'select'):
                    readable, _, _ = select.select([server_process.stdout, server_process.stderr], [], [], 0.1)
                    for stream in readable:
                        output = stream.read()
                        if output:
                            logger.error(f"Server output:\n{output}")
            except:
                logger.error("Could not read server output")
        else:
            logger.error(f"Server process exited with code {server_process.returncode}")

    return False


def start_local_server(config_name: str, task_id: int, base_port: int, log_file: Optional[Path] = None) -> tuple:
    """Start a local Python server process.

    Args:
        config_name: Configuration/task name
        task_id: Globally unique task ID (used for port assignment)
        base_port: Base port number to use
        log_file: Optional path to redirect server logs

    Returns:
        Tuple of (process, port, log_file_handle)
        - process: subprocess.Popen object
        - port: Port number the server is listening on
        - log_file_handle: File handle for the log file (or None)
    """
    # Find an available port starting from base_port + task_id
    # This handles cases where ports are already in use
    preferred_port = base_port + task_id
    host_port = find_available_port(preferred_port, max_attempts=100)

    if host_port != preferred_port:
        logger.warning(f"Preferred port {preferred_port} not available, using {host_port} instead")

    logger.info(f"Starting local server for {config_name} (task {task_id}) on port {host_port}")

    # Get project root (parent of inference directory)
    project_root = Path(__file__).parent.parent

    # Start server as subprocess
    server_cmd = [
        "python", "-u",  # -u for unbuffered output
        str(project_root / "gem" / "server" / "http_server.py"),
        "--host", "0.0.0.0",
        "--port", str(host_port),
        "--workspace-base", str(project_root / "outputs"),
        "--log-level", "DEBUG"
    ]

    # Note: We don't pass --log-file to the server anymore.
    # Instead, we redirect subprocess stdout/stderr to capture all server output.

    logger.debug(f"Server command: {' '.join(server_cmd)}")

    try:
        # Determine where to redirect output
        log_file_handle = None
        if log_file:
            # Create directory if it doesn't exist
            log_file.parent.mkdir(parents=True, exist_ok=True)
            logger.info(f"Server logs will be written to: {log_file}")

            # Create the file first to ensure it exists
            log_file.touch(exist_ok=True)
            logger.info(f"Server log file created/verified: {log_file}")

            # Open log file for writing with line buffering
            try:
                log_file_handle = open(log_file, 'w', buffering=1)  # Line buffered
                logger.info(f"Successfully opened log file handle: {log_file}")

                # Write initial marker and flush
                log_file_handle.write(f"=== Server Log Started at {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                log_file_handle.flush()
                os.fsync(log_file_handle.fileno())

                # Verify file exists and has content
                if log_file.exists():
                    size = log_file.stat().st_size
                    logger.info(f"Server log file verified: {log_file} ({size} bytes)")
                else:
                    logger.error(f"Server log file not found after creation: {log_file}")

            except Exception as e:
                logger.error(f"Failed to open log file {log_file}: {e}")
                raise

            # Start server process with stdout/stderr redirected to file
            process = subprocess.Popen(
                server_cmd,
                stdout=log_file_handle,
                stderr=log_file_handle,
                text=True
            )
            logger.info(f"Server process started with PID {process.pid}, output redirected to {log_file}")
        else:
            # No log file - use PIPE
            process = subprocess.Popen(
                server_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            logger.info(f"Server process started with PID {process.pid}, output to PIPE")

        logger.info(f"Local server started with PID {process.pid} on port {host_port}")
        return process, host_port, log_file_handle

    except Exception as e:
        logger.error(f"Failed to start local server: {e}")
        if log_file_handle:
            try:
                log_file_handle.close()
            except:
                pass
        raise RuntimeError(f"Failed to start local server: {e}") from e


def stop_local_server(process: subprocess.Popen, log_file_handle=None):
    """Stop a local server process.

    Args:
        process: The subprocess.Popen object for the server
        log_file_handle: Optional file handle to close
    """
    if process is None:
        return

    logger.info(f"Stopping local server (PID {process.pid})...")

    try:
        # Terminate the process
        process.terminate()

        # Wait for it to exit (with timeout)
        try:
            process.wait(timeout=10)
            logger.info(f"Local server stopped (PID {process.pid})")
        except subprocess.TimeoutExpired:
            # If it doesn't exit gracefully, kill it
            logger.warning(f"Server didn't stop gracefully, killing it...")
            process.kill()
            process.wait()
            logger.info(f"Local server killed (PID {process.pid})")

    except Exception as e:
        logger.warning(f"Failed to stop local server: {e}")

    finally:
        # Close log file handle if provided
        if log_file_handle:
            try:
                # Flush any remaining buffered output
                log_file_handle.flush()
                log_file_handle.close()
                logger.debug("Server log file flushed and closed")
            except Exception as e:
                logger.warning(f"Failed to close log file: {e}")


def make_aihubmix_api_request(
    messages: List[Dict],
    model_name: str,
    aihubmix_api_keys: str,
    aihubmix_api_url: str = "https://aihubmix.com/v1/chat/completions",
    tools: Optional[List] = None,
    tool_choice: Optional[str] = None,
    max_retries: int = 200,
    temperature: float = 1.0,
    top_p: float = 1.0,
    max_tokens: int = 4096,
    max_context_size: Optional[int] = None,
    context_awareness: bool = False,
    reasoning_effort: Optional[str] = None,
    reasoning_max_tokens: Optional[int] = None,
    reasoning_enabled: bool = True,
    reasoning_exclude: bool = False,
):
    """Make AIHubMix API request with retry logic.

    Args:
        messages: The messages to send to the API
        model_name: Name of the model to use
        aihubmix_api_keys: API key(s) for AIHubMix (comma-separated)
        aihubmix_api_url: The AIHubMix API endpoint URL
        tools: Optional list of tools to include in the request
        tool_choice: Optional tool choice parameter
        max_retries: Maximum number of retry attempts
        temperature: Sampling temperature
        top_p: Top-p sampling parameter
        max_tokens: Maximum number of tokens to generate
        max_context_size: Maximum context size in tokens (if set, will trim messages to fit)
        context_awareness: If True, will also remove token usage user messages when trimming

    Returns:
        Processed response object with type and data
    """
    # Determine API keys to use
    api_keys = []
    if isinstance(aihubmix_api_keys, list):
        api_keys = aihubmix_api_keys
    elif isinstance(aihubmix_api_keys, str) and ',' in aihubmix_api_keys:
        api_keys = aihubmix_api_keys.split(',')
    else:
        api_keys = [aihubmix_api_keys]

    # Randomly select an API key for this request
    current_api_key = random.choice(api_keys)

    # Prepare headers for API request
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + str(current_api_key)
    }

    print(f"Headers: {headers}")

    # Track whether messages were trimmed
    trimmed_messages = None
    trim_info = None  # Store trim information
    original_message_count = len(messages)

    # Prepare request data
    json_data = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens
    }

    # Add reasoning control parameters for OpenAI models that support reasoning
    # Convert empty strings to None for proper handling
    if reasoning_effort == "":
        reasoning_effort = None
    if reasoning_max_tokens == "":
        reasoning_max_tokens = None

    if reasoning_effort is not None or reasoning_max_tokens is not None:
        reasoning_config = {}

        # Set reasoning effort or max_tokens
        if reasoning_effort is not None:
            reasoning_config["effort"] = reasoning_effort
        elif reasoning_max_tokens is not None:
            reasoning_config["max_tokens"] = reasoning_max_tokens

        # Set enabled flag (default: inferred from effort or max_tokens)
        reasoning_config["enabled"] = reasoning_enabled

        # Set exclude flag (default: false)
        reasoning_config["exclude"] = reasoning_exclude

        json_data["reasoning"] = reasoning_config

    # Estimate tokens before making the API call
    try:
        import tiktoken
        # Get tokenizer
        try:
            tokenizer = tiktoken.encoding_for_model(model_name)
        except:
            tokenizer = tiktoken.get_encoding("cl100k_base")

        # Calculate tokens for messages
        messages_str = json.dumps(messages, ensure_ascii=False)
        messages_tokens = len(tokenizer.encode(messages_str, disallowed_special=()))

        # Calculate tokens for tools if provided
        tools_tokens = 0
        if tools:
            tools_str = json.dumps(tools, ensure_ascii=False)
            tools_tokens = len(tokenizer.encode(tools_str, disallowed_special=()))

        total_tokens = messages_tokens + tools_tokens

        # Trim messages if max_context_size is set and exceeded
        if max_context_size is not None and total_tokens > max_context_size:
            print(f"[Trim] Context size exceeded: {total_tokens} > {max_context_size}, trimming messages...")

            # Keep system and user messages, remove older tool results
            kept_messages = []
            removed_count = 0

            # Always keep the first user message (task description)
            first_user_msg = None
            if messages and messages[0].get("role") == "user":
                first_user_msg = messages[0]
                kept_messages.append(first_user_msg)

            # Process remaining messages from newest to oldest
            for msg in reversed(messages[1:] if first_user_msg else messages):
                # Skip token usage messages if context_awareness is enabled
                if context_awareness and msg.get("role") == "user":
                    content = msg.get("content", "")
                    if isinstance(content, str) and "Current token usage:" in content:
                        removed_count += 1
                        continue

                # Add message
                kept_messages.insert(1 if first_user_msg else 0, msg)

                # Recalculate tokens
                kept_str = json.dumps(kept_messages, ensure_ascii=False)
                kept_tokens = len(tokenizer.encode(kept_str, disallowed_special=()))
                current_total = kept_tokens + tools_tokens

                # Stop if we're under the limit
                if current_total <= max_context_size:
                    break
                else:
                    # Remove the message we just added
                    kept_messages.pop(1 if first_user_msg else 0)
                    removed_count += 1

            trimmed_messages = kept_messages
            trim_info = {
                "original_count": original_message_count,
                "trimmed_count": len(kept_messages),
                "removed_count": removed_count,
                "original_tokens": total_tokens,
                "trimmed_tokens": current_total if 'current_total' in locals() else kept_tokens + tools_tokens
            }

            print(f"[Trim] Removed {removed_count} messages, kept {len(kept_messages)} messages")
            print(f"[Trim] Token reduction: {total_tokens} -> {trim_info['trimmed_tokens']}")

            # Update messages to use trimmed version
            messages = trimmed_messages
            json_data["messages"] = messages

    except Exception as e:
        print(f"Warning: Failed to calculate tokens for trimming: {e}")

    # Add tools if provided
    if tools:
        json_data["tools"] = tools
        if tool_choice:
            json_data["tool_choice"] = tool_choice

    # Make request with retry logic
    for attempt in range(max_retries):
        try:
            response = requests.post(
                aihubmix_api_url,
                json=json_data,
                headers=headers,
                timeout=600
            )
            response.raise_for_status()

            # Parse response
            response_data = response.json()

            # Check for error in response
            if "error" in response_data:
                error_msg = response_data["error"].get("message", "Unknown error")
                print(f"API error: {error_msg}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    raise RuntimeError(f"API error: {error_msg}")

            # Extract message from response
            if "choices" in response_data and len(response_data["choices"]) > 0:
                choice = response_data["choices"][0]
                message = choice.get("message", {})

                # Build response object
                result = {
                    "type": "success",
                    "call_messages": message,
                    "raw_response": response_data,
                    "trimmed_messages": trimmed_messages,
                    "trim_info": trim_info
                }

                return result
            else:
                raise RuntimeError(f"Unexpected response format: {response_data}")

        except (RequestException, HTTPError) as e:
            print(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")

            # Fail fast on client errors that won't recover with retries
            # 400: Bad Request (typically context too long)
            # 413: Payload Too Large
            # 422: Unprocessable Entity
            if isinstance(e, HTTPError) and e.response is not None and e.response.status_code in (400, 413, 422):
                error_detail = ""
                try:
                    error_detail = e.response.text[:500]  # Get first 500 chars of error
                except:
                    pass
                status_code = e.response.status_code
                print(f"{status_code} Client Error - failing fast (non-recoverable). Detail: {error_detail}")
                raise RuntimeError(f"API request failed with {status_code} (non-recoverable client error): {e}") from e

            if attempt < max_retries - 1:
                # Cap exponential backoff at 60 seconds to prevent unbounded waits
                wait_time = min(2 ** attempt, 60)
                print(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            else:
                raise RuntimeError(f"API request failed after {max_retries} attempts") from e

    raise RuntimeError(f"API request failed after {max_retries} attempts")


def perform_thinking_reset(messages: List[Dict], keep_thinking: int = 1) -> tuple:
    """Remove reasoning_content from older assistant messages.

    Args:
        messages: List of messages
        keep_thinking: Number of most recent assistant messages to keep reasoning_content for

    Returns:
        Tuple of (modified_messages, reset_info)
    """
    # Find all assistant message indices (in reverse order)
    assistant_indices = []
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "assistant":
            assistant_indices.append(i)

    # Keep reasoning_content for the most recent keep_thinking assistant messages
    kept_indices = set(assistant_indices[:keep_thinking])

    # Remove reasoning_content from older assistant messages
    removed_count = 0
    removed_tokens = 0

    for i in assistant_indices[keep_thinking:]:
        msg = messages[i]
        if "reasoning_content" in msg or "reasoning" in msg:
            # Calculate tokens removed
            try:
                import tiktoken
                try:
                    tokenizer = tiktoken.encoding_for_model("gpt-4")
                except:
                    tokenizer = tiktoken.get_encoding("cl100k_base")

                reasoning_text = msg.get("reasoning_content") or msg.get("reasoning", "")
                if reasoning_text:
                    removed_tokens += len(tokenizer.encode(str(reasoning_text), disallowed_special=()))
            except:
                pass

            # Remove reasoning fields
            if "reasoning_content" in msg:
                del msg["reasoning_content"]
            if "reasoning" in msg:
                del msg["reasoning"]

            removed_count += 1

    reset_info = {
        "removed_count": removed_count,
        "removed_tokens": removed_tokens,
        "kept_count": keep_thinking
    }

    return messages, reset_info


def perform_context_reset(messages: List[Dict], reset_ratio: float, keep_last_tool_call: bool = True) -> tuple:
    """Remove older tool calls and results from messages.

    Args:
        messages: List of messages
        reset_ratio: Ratio of tool calls to remove (0.0 to 1.0)
        keep_last_tool_call: If True, always keep the most recent tool call

    Returns:
        Tuple of (modified_messages, reset_info)
    """
    # Find all tool call pairs (assistant with tool_calls + corresponding tool results)
    tool_call_pairs = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg.get("role") == "assistant" and "tool_calls" in msg:
            # Found an assistant message with tool calls
            # Collect all following tool result messages
            tool_results = []
            j = i + 1
            while j < len(messages) and messages[j].get("role") == "tool":
                tool_results.append(j)
                j += 1

            tool_call_pairs.append({
                "assistant_idx": i,
                "tool_result_indices": tool_results
            })
            i = j
        else:
            i += 1

    # Calculate how many to remove
    total_pairs = len(tool_call_pairs)
    num_to_remove = int(total_pairs * reset_ratio)

    # Keep at least the last tool call if requested
    if keep_last_tool_call and num_to_remove >= total_pairs:
        num_to_remove = max(0, total_pairs - 1)

    # Collect indices to remove (oldest tool calls first)
    indices_to_remove = set()
    for pair in tool_call_pairs[:num_to_remove]:
        indices_to_remove.add(pair["assistant_idx"])
        indices_to_remove.update(pair["tool_result_indices"])

    # Build new messages list
    new_messages = []
    for i, msg in enumerate(messages):
        if i not in indices_to_remove:
            new_messages.append(msg)

    reset_info = {
        "original_count": len(messages),
        "new_count": len(new_messages),
        "removed_count": len(indices_to_remove),
        "tool_pairs_removed": num_to_remove,
        "tool_pairs_total": total_pairs
    }

    return new_messages, reset_info


def run_single_task(
    task_id: int,
    config_id: int,
    run_id: int,
    base_task_dir: str,
    output_dir: str,
    config_name: str,
    config: Dict[str, Any],
    api_key: str,
    base_url: str,
    model: str,
    max_tool_uses: int = 500,
    max_tokens: int = 32768,
    timeout: int = 600,
    max_retries: int = 10,
    initial_retry_delay: float = 2.0,
    reset_size: Optional[int] = None,
    reset_ratio: float = 0.5,
    context_reset: bool = False,
    context_summary: bool = False,
    context_awareness: bool = False,
    max_context_size: Optional[int] = None,
    memory_warning_threshold: float = 0.8,
    thinking_reset: bool = False,
    keep_thinking: int = 1,
    reasoning_effort: Optional[str] = None,
    reasoning_max_tokens: Optional[int] = None,
    reasoning_enabled: bool = True,
    reasoning_exclude: bool = False,
    execution_mode: str = "sandbox",
    base_port: int = 9000,
    docker_image: str = "loca-bench:latest",
    container_runtime: str = "docker",
):
    """Run a single task with remote environment (local server or container).

    Args:
        task_id: Global unique identifier for this task instance
        config_id: Configuration group ID
        run_id: Run number within this configuration
        base_task_dir: Base directory for task data
        output_dir: Directory to save results
        config_name: Name of the configuration/task (used for directory naming)
        config: Full configuration dictionary with env_class, env_params, mcp_servers
        api_key: API key for the model
        base_url: Base URL for the API
        model: Model name to use
        max_tool_uses: Maximum number of tool uses
        max_tokens: Maximum tokens for generation
        timeout: Request timeout in seconds
        max_retries: Maximum API retry attempts
        initial_retry_delay: Initial delay for retry in seconds
        reset_size: Token threshold for context management (None to disable all management)
        reset_ratio: Ratio of tool calls to remove during reset (0.0 to 1.0)
        context_reset: If True, remove old tool calls when exceeding token limit
        context_summary: If True, generate summary when exceeding token limit
        context_awareness: If True, inform the model about token budget and usage at each step
        max_context_size: Maximum context size in tokens (if set, will trim messages to fit)
        memory_warning_threshold: Threshold ratio (0.0-1.0) for memory warning when memory_tool is enabled.
        thinking_reset: If True, clear reasoning_content from assistant messages when exceeding token limit
        keep_thinking: Number of most recent assistant messages to keep reasoning_content for (default: 1)
        execution_mode: Execution mode - "local" (local server) or "sandbox" (container) (default: "sandbox")
        base_port: Base port number for servers (default: 9000)
        docker_image: Container image to use for sandbox mode (default: "loca-bench:latest")
        container_runtime: Container runtime to use - "docker" or "podman" (default: "docker")

    Returns:
        Dictionary with task results
    """
    task_label = f"Config{config_id}-Run{run_id}"
    print(f"[Task {task_id} | {task_label}] Starting...")
    print(f"[Task {task_id} | {task_label}] Configuration: {config_name}")
    print(f"[Task {task_id} | {task_label}] Execution mode: {execution_mode}")

    # Create isolated directories for this task
    task_workspace = Path(base_task_dir) / config_name / f"run_{run_id}"
    task_workspace.mkdir(parents=True, exist_ok=True)

    # Define workspace paths (env will create these during reset())
    local_db_dir = task_workspace / "local_db"
    agent_workspace = task_workspace / "agent_workspace"
    memory_dir = agent_workspace / "memory"

    print(f"[Task {task_id} | {task_label}] Task workspace: {task_workspace}")

    # Create TEMPORARY client log file FIRST (will be moved after env init)
    # This ensures errors during server startup/env init are captured
    import tempfile
    temp_dir = Path(tempfile.gettempdir())
    temp_client_log = temp_dir / f"loca_client_{task_id}_{run_id}.log"

    # Set up client logger with temporary file
    task_logger = logging.getLogger(f"task_{task_id}")
    task_logger.setLevel(logging.DEBUG)
    task_logger.handlers.clear()
    task_logger.propagate = False

    client_file_handle = open(temp_client_log, 'w', buffering=1)
    client_file_handler = logging.StreamHandler(client_file_handle)
    client_file_handler.setLevel(logging.DEBUG)
    client_file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    task_logger.addHandler(client_file_handler)

    # Log task start (before any operations that could fail)
    task_logger.info(f"=== Task {task_id} | {task_label} ===")
    task_logger.info(f"Configuration: {config_name}")
    task_logger.info(f"Execution mode: {execution_mode}")
    task_logger.info(f"Task workspace: {task_workspace}")
    task_logger.info(f"Temporary client log: {temp_client_log}")
    print(f"[Task {task_id} | {task_label}] Client log created: {temp_client_log}")

    episode = []
    full_messages_history = []
    reset_events = []
    summary_events = []
    trim_events = []
    thinking_reset_events = []
    initial_user_message = None
    memory_warning_issued = False

    # Track cleanup resources based on execution mode
    container_name = None
    server_process = None
    server_log_handle = None
    remote_client = None
    obs = None
    info = None
    tools = None

    # Retry configuration for server initialization
    MAX_INIT_RETRIES = 3
    init_attempt = 0

    try:
        # Retry loop for server start + initialization
        while init_attempt < MAX_INIT_RETRIES:
            init_attempt += 1

            try:
                # Start server (Docker container or local process) and create remote client
                if execution_mode == "sandbox":
                    # Sandbox mode: Use container
                    print(f"[Task {task_id} | {task_label}] Starting {container_runtime} container with image {docker_image} (attempt {init_attempt}/{MAX_INIT_RETRIES})...")

                    # Create TEMPORARY log file for server (will be moved after env init)
                    import tempfile
                    temp_dir = Path(tempfile.gettempdir())
                    temp_server_log = temp_dir / f"loca_server_{task_id}_{run_id}_attempt{init_attempt}.log"

                    container_name, port, container_process, server_log_handle = start_docker_container(
                        config_name, task_id, run_id, base_port, task_workspace, docker_image, container_runtime,
                        log_file=temp_server_log
                    )
                    print(f"[Task {task_id} | {task_label}] Container started on port {port} (PID {container_process.pid})")
                    print(f"[Task {task_id} | {task_label}] Temporary server log: {temp_server_log}")

                    # Wait for container to become healthy
                    print(f"[Task {task_id} | {task_label}] Waiting for container to start (logs: {temp_server_log})...")
                    if not wait_for_server_health(port, server_process=container_process):
                        # Give the log file a moment to be written
                        time.sleep(0.5)

                        # Try to show the log file content
                        print(f"[Task {task_id} | {task_label}] Container failed to start. Check logs at: {temp_server_log}")
                        if temp_server_log.exists():
                            print(f"[Task {task_id} | {task_label}] Last 50 lines of server log:")
                            try:
                                with open(temp_server_log, 'r') as f:
                                    lines = f.readlines()
                                    for line in lines[-50:]:
                                        print(f"  {line.rstrip()}")
                            except Exception as e:
                                print(f"  Could not read log file: {e}")
                        else:
                            print(f"  Log file does not exist at {temp_server_log}")
                        raise RuntimeError(f"Container {container_name} failed to become healthy. Check {temp_server_log}")

                    print(f"[Task {task_id} | {task_label}] Docker container ready")

                elif execution_mode == "local":
                    # Local mode: Use local Python server process
                    print(f"[Task {task_id} | {task_label}] Starting local server (attempt {init_attempt}/{MAX_INIT_RETRIES})...")

                    # Create TEMPORARY log file for server (will be moved after env init)
                    import tempfile
                    temp_dir = Path(tempfile.gettempdir())
                    temp_server_log = temp_dir / f"loca_server_{task_id}_{run_id}_attempt{init_attempt}.log"

                    server_process, port, server_log_handle = start_local_server(config_name, task_id, base_port, log_file=temp_server_log)
                    print(f"[Task {task_id} | {task_label}] Server started on port {port} (PID {server_process.pid})")
                    print(f"[Task {task_id} | {task_label}] Temporary server log: {temp_server_log}")

                    # Wait for server to become healthy
                    print(f"[Task {task_id} | {task_label}] Waiting for server to start (logs: {temp_server_log})...")
                    if not wait_for_server_health(port, server_process=server_process):
                        # Give the log file a moment to be written
                        time.sleep(0.5)

                        # Try to show the log file content
                        print(f"[Task {task_id} | {task_label}] Server failed to start. Check logs at: {temp_server_log}")
                        if temp_server_log.exists():
                            print(f"[Task {task_id} | {task_label}] Last 50 lines of server log:")
                            try:
                                with open(temp_server_log, 'r') as f:
                                    lines = f.readlines()
                                    for line in lines[-50:]:
                                        print(f"  {line.rstrip()}")
                            except Exception as e:
                                print(f"  Could not read log file: {e}")
                        else:
                            print(f"  Log file does not exist at {temp_server_log}")
                        raise RuntimeError(f"Local server on port {port} failed to become healthy. Check {temp_server_log}")

                    print(f"[Task {task_id} | {task_label}] Local server ready")

                else:
                    raise ValueError(f"Invalid execution mode: {execution_mode}. Must be 'local' or 'sandbox'")

                # Create remote environment client
                # For sandbox mode, translate host paths to container paths
                server_url = f"http://localhost:{port}"
                print(f"[Task {task_id} | {task_label}] Creating remote client for server at {server_url}")

                if execution_mode == "sandbox":
                    # Container has volume mounted at /workspace/outputs/tasks/{config_name}/run_{run_id}
                    container_task_workspace = f"/workspace/outputs/tasks/{config_name}/run_{run_id}"
                    container_agent_workspace = f"/workspace/outputs/tasks/{config_name}/run_{run_id}/agent_workspace"
                    print(f"[Task {task_id} | {task_label}] Using container paths: {container_task_workspace}")
                else:
                    container_task_workspace = str(task_workspace)
                    container_agent_workspace = str(agent_workspace)

                remote_client = RemoteEnvironmentClient(
                    server_url=server_url,
                    config=config,
                    task_workspace=container_task_workspace,
                    agent_workspace=container_agent_workspace,
                    timeout=timeout
                )

                # Initialize remote environment (this will clear task_workspace!)
                print(f"[Task {task_id} | {task_label}] Initializing remote environment...")
                task_logger.info(f"Initializing remote environment (attempt {init_attempt}/{MAX_INIT_RETRIES})")
                obs, info = remote_client.reset()
                tools = remote_client.get_tools()

                # If we got here, initialization succeeded - break out of retry loop
                print(f"[Task {task_id} | {task_label}] ✅ Remote environment initialized successfully")
                task_logger.info(f"Remote environment initialized successfully on attempt {init_attempt}")
                break

            except Exception as init_error:
                # Determine if this is a timeout error
                is_timeout = "Timeout" in str(init_error) or "timed out" in str(init_error).lower()
                error_type = "⏱️  TIMEOUT" if is_timeout else "ERROR"

                # Log which task and config failed
                error_msg = f"❌ {error_type}: Initialization failed for task '{config_name}' (run {run_id}): {init_error}"
                print(f"[Task {task_id} | {task_label}] {error_msg}")
                task_logger.error(error_msg)

                # Clean up the failed server before retrying
                if execution_mode == "sandbox" and container_name:
                    # Logs are already being written to temp_server_log in real-time
                    print(f"[Task {task_id} | {task_label}] Container logs available at: {temp_server_log}")
                    print(f"[Task {task_id} | {task_label}] Stopping failed container {container_name}...")
                    try:
                        stop_docker_container(container_name, container_runtime,
                                            process=container_process if 'container_process' in locals() else None,
                                            log_file_handle=server_log_handle if 'server_log_handle' in locals() else None)
                    except Exception as cleanup_error:
                        print(f"[Task {task_id} | {task_label}] Warning: Failed to stop container: {cleanup_error}")
                    container_name = None
                    container_process = None
                    server_log_handle = None

                elif execution_mode == "local" and server_process:
                    print(f"[Task {task_id} | {task_label}] Stopping failed server process (PID {server_process.pid})...")
                    try:
                        stop_local_server(server_process, server_log_handle)
                    except Exception as cleanup_error:
                        print(f"[Task {task_id} | {task_label}] Warning: Failed to stop server: {cleanup_error}")
                    server_process = None
                    server_log_handle = None

                # For timeouts, don't retry - they usually indicate stuck processes
                if is_timeout:
                    print(f"[Task {task_id} | {task_label}] ⏱️  Timeout detected - not retrying (likely stuck process)")
                    task_logger.error("Timeout during initialization - environment preprocessing is taking too long or hanging")
                    raise RuntimeError(
                        f"⏱️  Timeout: Task '{config_name}' (run {run_id}) initialization exceeded timeout. "
                        f"Environment preprocessing is stuck or taking too long."
                    ) from init_error

                # If this was the last attempt, re-raise the error
                if init_attempt >= MAX_INIT_RETRIES:
                    print(f"[Task {task_id} | {task_label}] ❌ All {MAX_INIT_RETRIES} initialization attempts failed")
                    task_logger.error(f"All {MAX_INIT_RETRIES} initialization attempts failed")
                    raise RuntimeError(f"Failed to initialize task '{config_name}' (run {run_id}) after {MAX_INIT_RETRIES} attempts") from init_error

                # Wait a bit before retrying
                retry_wait = 2 ** init_attempt  # Exponential backoff: 2s, 4s, 8s
                print(f"[Task {task_id} | {task_label}] Retrying in {retry_wait} seconds...")
                time.sleep(retry_wait)

        # Verify we got valid initialization results
        if obs is None or tools is None:
            raise RuntimeError(f"Initialization succeeded but obs or tools is None")

        print(f"[Task {task_id} | {task_label}] Remote environment initialized")
        print(f"[Task {task_id} | {task_label}] Initial observation length: {len(obs)}")

        # NOW create logs directory and move temp logs (after env.reset() which clears task_workspace)
        log_dir = task_workspace / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        client_log_file = log_dir / "client.log"

        # Move temp client log to final location
        task_logger.info(f"Environment initialized - loaded {len(tools) if tools else 0} tools")
        task_logger.info(f"Initial observation length: {len(obs)} chars")
        task_logger.info(f"Moving client log from {temp_client_log} to {client_log_file}")

        # Flush temp log before moving
        client_file_handle.flush()
        os.fsync(client_file_handle.fileno())
        client_file_handle.close()

        # Move the temp file to final location
        import shutil
        shutil.move(str(temp_client_log), str(client_log_file))

        # Reopen the log file at its new location
        client_file_handle = open(client_log_file, 'a', buffering=1)

        # Update logger handler to use new file handle
        task_logger.handlers.clear()
        client_file_handler = logging.StreamHandler(client_file_handle)
        client_file_handler.setLevel(logging.DEBUG)
        client_file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        task_logger.addHandler(client_file_handler)

        task_logger.info(f"Client log moved to: {client_log_file}")

        # Flush to ensure logs are written
        client_file_handle.flush()
        os.fsync(client_file_handle.fileno())

        print(f"[Task {task_id} | {task_label}] Logs created at: {log_dir}")

        # Move server log to logs directory if it exists
        if 'server_log_handle' in locals() and server_log_handle:
            try:
                # Get the temp server log path from the file handle
                temp_server_log = Path(server_log_handle.name)
                final_server_log = log_dir / "server.log"

                # Close the temp file handle first
                server_log_handle.flush()
                server_log_handle.close()

                # Move the file
                if temp_server_log.exists():
                    import shutil
                    shutil.move(str(temp_server_log), str(final_server_log))
                    task_logger.info(f"Server log moved to: {final_server_log}")
                    print(f"[Task {task_id} | {task_label}] Server log: {final_server_log}")

                # Reopen for continued logging (though server is already running)
                server_log_handle = None  # Can't redirect running process
            except Exception as e:
                task_logger.warning(f"Failed to move server log: {e}")

        # Save tools information
        tools_info = tools if tools else None

        # Check if memory_tool is included in config
        has_memory_tool = any(
            server_config.get("type") in ["memory_tool", "memory-tool"] and server_config.get("enabled", True)
            for server_config in config.get("mcp_servers", {}).values()
        )

        # Build the user prompt with optional enhancements
        enhanced_user_prompt = obs

        # Add memory protocol if memory_tool is included
        if has_memory_tool:
            memory_protocol = (
                "\n\n"
                "IMPORTANT: ALWAYS VIEW YOUR MEMORY DIRECTORY BEFORE DOING ANYTHING ELSE.\n"
                "MEMORY PROTOCOL:\n"
                "1. Use the `view` command of your `memory_tool` to check for earlier progress.\n"
                "2. ... (work on the task) ...\n"
                "     - As you make progress, record status / progress / thoughts etc in your memory.\n"
                "ASSUME INTERRUPTION: Your context window might be reset at any moment, so you risk losing any progress that is not recorded in your memory directory."
            )
            enhanced_user_prompt += memory_protocol
            print(f"[Task {task_id} | {task_label}] Memory tool detected: Added MEMORY PROTOCOL to user prompt")

        # Add context awareness if enabled
        if context_awareness and max_context_size is not None:
            display_context_size = max_context_size

            context_notice = (
                "\n\n"
                f"You need to complete the task within the following context window size:\n"
                f"<budget:token_budget>{display_context_size}</budget:token_budget>\n\n"
                f"Your context window will be automatically compacted as it approaches its limit, "
                f"allowing you to continue working indefinitely from where you left off. "
                f"Therefore, do not stop tasks early due to token budget concerns."
            )
            enhanced_user_prompt += context_notice
            print(f"[Task {task_id} | {task_label}] Context awareness enabled: Added token budget ({display_context_size}) to user prompt")

        messages = [{"role": "user", "content": enhanced_user_prompt}]
        initial_user_message = {"role": "user", "content": enhanced_user_prompt}
        full_messages_history.append(initial_user_message.copy())

        # Save trajectory to task_workspace (not separate output directory)
        timestamp = int(time.time())
        save_file = task_workspace / f"{config_name}_run{run_id}-episode.json"
        task_logger.info(f"Trajectory will be saved to: {save_file}")

        # Run interaction loop
        done = False
        step_count = 0
        tool_use_count = 0

        while not done and tool_use_count < max_tool_uses:
            step_count += 1
            print(f"[Task {task_id} | {task_label}] Step {step_count}")
            task_logger.info(f"=== Step {step_count} ===")
            task_logger.info(f"Current message count: {len(messages)}, Tool use count: {tool_use_count}/{max_tool_uses}")

            # Add cache control for Claude models at specific steps
            if "claude" in model.lower() and step_count in [2, 4, 8, 16]:
                print(f"[Task {task_id} | {task_label}] Adding cache control at step {step_count}")
                cache_message = {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "function called",
                            "cache_control": {"type": "ephemeral"}
                        }
                    ]
                }
                messages.append(cache_message)

            # Make API request
            task_logger.info(f"Calling LLM API: {model}")
            response = make_aihubmix_api_request(
                messages=messages,
                model_name=model,
                aihubmix_api_keys=api_key,
                aihubmix_api_url=f"{base_url}/chat/completions",
                tools=tools if tools else None,
                max_retries=max_retries,
                temperature=1.0,
                top_p=1.0,
                max_tokens=max_tokens,
                max_context_size=max_context_size,
                context_awareness=context_awareness,
                reasoning_effort=reasoning_effort,
                reasoning_max_tokens=reasoning_max_tokens,
                reasoning_enabled=reasoning_enabled,
                reasoning_exclude=reasoning_exclude,
            )
            task_logger.info(f"LLM API response received")

            # Update messages if they were trimmed
            if 'trimmed_messages' in response and response['trimmed_messages'] is not None:
                original_count = len(messages)
                original_messages = messages
                messages = response['trimmed_messages']
                print(f"[Task {task_id} | {task_label}] Messages updated after trimming: {original_count} -> {len(messages)}")

                # Check if memory warning was trimmed away
                if memory_warning_issued:
                    had_memory_warning = any(
                        msg.get('role') == 'user' and
                        isinstance(msg.get('content', ''), str) and
                        '**You are nearing the context window limit.**' in msg.get('content', '')
                        for msg in original_messages
                    )
                    has_memory_warning = any(
                        msg.get('role') == 'user' and
                        isinstance(msg.get('content', ''), str) and
                        '**You are nearing the context window limit.**' in msg.get('content', '')
                        for msg in messages
                    )
                    if had_memory_warning and not has_memory_warning:
                        memory_warning_issued = False
                        print(f"[Task {task_id} | {task_label}] Memory warning was trimmed away, resetting flag")

                # Record trim event
                if 'trim_info' in response and response['trim_info'] is not None:
                    import copy
                    trim_event = {
                        'step': step_count,
                        'trim_info': copy.deepcopy(response['trim_info']),
                        'context': 'main_api_call'
                    }
                    trim_events.append(trim_event)
                    print(f"[Task {task_id} | {task_label}] Trim event recorded: removed {response['trim_info']['removed_count']} messages")

            # Check if response has call_messages
            if 'call_messages' not in response:
                print(f"ERROR: Response missing 'call_messages' key. Response: {response}")
                call_messages = {
                    "role": "assistant",
                    "content": f"Error: Invalid response format - {response.get('type', 'unknown')}: {response.get('data', ['Unknown error'])}"
                }
            else:
                call_messages = response['call_messages']

            # Ensure all tool_calls have arguments field
            if 'tool_calls' in call_messages and call_messages['tool_calls']:
                for tool_call in call_messages['tool_calls']:
                    if 'function' in tool_call:
                        if 'arguments' not in tool_call['function']:
                            tool_call['function']['arguments'] = "{}"
                        elif tool_call['function']['arguments'] == "":
                            tool_call['function']['arguments'] = "{}"

            # Add assistant's message to conversation
            messages.append(call_messages)
            full_messages_history.append(call_messages.copy())

            # Log LLM response to file only (not terminal)
            task_logger.debug(f"LLM Response: {response}")

            # Execute tools via remote client
            if 'tool_calls' in call_messages and call_messages['tool_calls']:
                tool_calls = call_messages['tool_calls']
                tool_use_count += len(tool_calls)

                # Check if claim_done was called (tool name can be "claim_done" or "claim_done_claim_done")
                claim_done_called = any(
                    "claim_done" in tc.get("function", {}).get("name", "")
                    for tc in tool_calls
                )

                if claim_done_called:
                    # Evaluate task completion
                    task_logger.info("claim_done called, evaluating task")
                    obs, reward, terminated, truncated, info = remote_client.evaluate()
                    done = terminated or truncated
                    task_logger.info(f"Evaluation complete: reward={reward}, terminated={terminated}, truncated={truncated}")
                    task_logger.info(f"Evaluation info: {info}")

                    # Log evaluation results to file only (not terminal)
                    task_logger.debug(f"Evaluation - obs: {obs}")
                    task_logger.debug(f"Evaluation - reward: {reward}")
                    task_logger.debug(f"Evaluation - terminated: {terminated}")
                    task_logger.debug(f"Evaluation - truncated: {truncated}")
                    task_logger.debug(f"Evaluation - info: {info}")

                    # Create tool result message for claim_done
                    claim_done_call = next(
                        tc for tc in tool_calls
                        if "claim_done" in tc.get("function", {}).get("name", "")
                    )
                    tool_result = {
                        "role": "tool",
                        "tool_call_id": claim_done_call["id"],
                        "content": obs
                    }
                    messages.append(tool_result)
                    full_messages_history.append(tool_result)
                else:
                    # Execute tools remotely
                    task_logger.info(f"Executing {len(tool_calls)} tool calls remotely")
                    for tc in tool_calls:
                        task_logger.debug(f"  Tool: {tc.get('function', {}).get('name', 'unknown')}")
                    tool_results = remote_client.execute_tools(tool_calls)
                    task_logger.info(f"Tool execution complete, received {len(tool_results)} results")

                    # Log tool results to file only (not terminal)
                    task_logger.debug(f"Tool Results: {tool_results}")

                    # Add tool results to messages
                    messages.extend(tool_results)
                    full_messages_history.extend(tool_results)

                    # Add token usage information if context_awareness is enabled
                    if context_awareness and max_context_size is not None:
                        try:
                            import tiktoken
                            try:
                                tokenizer = tiktoken.encoding_for_model(model)
                            except:
                                tokenizer = tiktoken.get_encoding("cl100k_base")

                            # Calculate tokens for messages
                            messages_str = json.dumps(messages, ensure_ascii=False)
                            messages_tokens = len(tokenizer.encode(messages_str, disallowed_special=()))

                            # Calculate tokens for tools if provided
                            tools_tokens = 0
                            if tools:
                                tools_str = json.dumps(tools, ensure_ascii=False)
                                tools_tokens = len(tokenizer.encode(tools_str, disallowed_special=()))

                            current_tokens = messages_tokens + tools_tokens
                            display_context_size = max_context_size
                            remaining_tokens = display_context_size - current_tokens

                            # Add token usage warning message
                            token_usage_message = {
                                "role": "user",
                                "content": f"Current token usage:\n<system_warning>Token usage: {current_tokens}/{display_context_size}; {remaining_tokens} remaining</system_warning>"
                            }
                            messages.append(token_usage_message)
                            full_messages_history.append(token_usage_message)

                            print(f"[Task {task_id} | {task_label}] Context awareness: Token usage {current_tokens}/{display_context_size} ({remaining_tokens} remaining)")
                        except Exception as e:
                            print(f"[Task {task_id} | {task_label}] Warning: Failed to calculate tokens: {e}")
            else:
                # No tool calls, just text response - task might be done
                print(f"[Task {task_id} | {task_label}] No tool calls in response")

            # Check if context RESET is needed
            if context_reset and reset_size is not None and 'raw_response' in response:
                try:
                    import tiktoken
                    try:
                        tokenizer = tiktoken.encoding_for_model(model)
                    except:
                        tokenizer = tiktoken.get_encoding("cl100k_base")

                    # Calculate tokens for messages
                    messages_str = json.dumps(messages, ensure_ascii=False)
                    messages_tokens = len(tokenizer.encode(messages_str, disallowed_special=()))

                    # Calculate tokens for tools if provided
                    tools_tokens = 0
                    if tools:
                        tools_str = json.dumps(tools, ensure_ascii=False)
                        tools_tokens = len(tokenizer.encode(tools_str, disallowed_special=()))

                    total_tokens = messages_tokens + tools_tokens
                except Exception as e:
                    print(f"[Task {task_id} | {task_label}] Warning: Failed to calculate tokens: {e}")
                    usage = response.get('raw_response', {}).get('usage', {})
                    total_tokens = usage.get('total_tokens', 0)

                # Check if memory warning should be issued
                memory_warning_threshold_tokens = reset_size * memory_warning_threshold
                if has_memory_tool and not memory_warning_issued and total_tokens >= memory_warning_threshold_tokens and total_tokens < reset_size:
                    print(f"[Task {task_id} | {task_label}] Memory warning threshold reached ({total_tokens} >= {memory_warning_threshold_tokens:.0f})")

                    remaining_tokens = reset_size - total_tokens if reset_size else max_context_size - total_tokens

                    memory_warning_message = {
                        "role": "user",
                        "content": (
                            "<system_warning>\n\n"
                            "**You are nearing the context window limit.**\n\n"
                            "Your context will be automatically compacted soon.\n\n"
                            "Please save any important information from tool results into memory files before it is removed from the context. "
                            f"Token usage: {total_tokens}/{reset_size if reset_size else max_context_size}; {remaining_tokens} remaining"
                            "</system_warning>"
                        )
                    }
                    messages.append(memory_warning_message)
                    memory_warning_issued = True

                # Perform context reset if needed
                if total_tokens > reset_size:
                    print(f"[Task {task_id} | {task_label}] Context reset triggered: {total_tokens} > {reset_size}")
                    messages, reset_info = perform_context_reset(messages, reset_ratio, keep_last_tool_call=True)
                    reset_events.append({
                        'step': step_count,
                        'reset_info': reset_info
                    })
                    print(f"[Task {task_id} | {task_label}] Context reset: removed {reset_info['removed_count']} messages")

            # Check if thinking reset is needed
            if thinking_reset and reset_size is not None and 'raw_response' in response:
                try:
                    import tiktoken
                    try:
                        tokenizer = tiktoken.encoding_for_model(model)
                    except:
                        tokenizer = tiktoken.get_encoding("cl100k_base")

                    messages_str = json.dumps(messages, ensure_ascii=False)
                    messages_tokens = len(tokenizer.encode(messages_str, disallowed_special=()))

                    tools_tokens = 0
                    if tools:
                        tools_str = json.dumps(tools, ensure_ascii=False)
                        tools_tokens = len(tokenizer.encode(tools_str, disallowed_special=()))

                    total_tokens = messages_tokens + tools_tokens

                    if total_tokens > reset_size:
                        print(f"[Task {task_id} | {task_label}] Thinking reset triggered: {total_tokens} > {reset_size}")
                        messages, thinking_info = perform_thinking_reset(messages, keep_thinking)
                        thinking_reset_events.append({
                            'step': step_count,
                            'thinking_info': thinking_info
                        })
                        print(f"[Task {task_id} | {task_label}] Thinking reset: removed reasoning from {thinking_info['removed_count']} messages")
                except Exception as e:
                    print(f"[Task {task_id} | {task_label}] Warning: Failed to calculate tokens for thinking reset: {e}")

        # Task completed or max tool uses reached
        if tool_use_count >= max_tool_uses:
            print(f"[Task {task_id} | {task_label}] Max tool uses reached: {tool_use_count}")
            reward = 0.0
            info = {"error": "Max tool uses reached"}
        else:
            # Get final reward and info from last evaluation
            # Preserve reward if it was set during evaluation, otherwise try to get it from info
            if 'reward' not in locals():
                reward = info.get("reward", 0.0) if 'info' in locals() else 0.0
            if 'info' not in locals():
                info = {}

        # Save episode data
        episode_data = {
            "task_id": task_id,
            "config_id": config_id,
            "run_id": run_id,
            "config_name": config_name,
            "messages": full_messages_history,
            "steps": step_count,
            "tool_uses": tool_use_count,
            "final_reward": reward,
            "accuracy": info.get("accuracy", reward),
            "info": info,
            "tools": tools_info,
            "reset_events": reset_events,
            "summary_events": summary_events,
            "trim_events": trim_events,
            "thinking_reset_events": thinking_reset_events,
            "timestamp": timestamp
        }

        task_logger.info(f"Saving episode data to {save_file}")
        with open(save_file, "w") as f:
            json.dump(episode_data, f, indent=2)
        task_logger.info(f"Episode data saved successfully")

        print(f"[Task {task_id} | {task_label}] Completed successfully")
        print(f"[Task {task_id} | {task_label}] Final reward: {reward}")
        print(f"[Task {task_id} | {task_label}] Saved to: {save_file}")

        task_logger.info(f"=== Task Completed Successfully ===")
        task_logger.info(f"Final reward: {reward}")
        task_logger.info(f"Steps: {step_count}, Tool uses: {tool_use_count}")
        task_logger.info(f"Accuracy: {info.get('accuracy', reward)}")

        return {
            "task_id": task_id,
            "config_id": config_id,
            "run_id": run_id,
            "status": "success",
            "steps": step_count,
            "tool_uses": tool_use_count,
            "final_reward": reward,
            "accuracy": info.get("accuracy", reward),
            "save_file": str(save_file)
        }

    except Exception as e:
        print(f"[Task {task_id} | {task_label}] Error: {e}")
        import traceback
        traceback.print_exc()

        # Try to log error if logger exists
        if 'task_logger' in locals():
            try:
                task_logger.error(f"Task failed with error: {e}")
                task_logger.error(f"Traceback:\n{traceback.format_exc()}")
                # Force flush to ensure error is written
                if 'client_file_handle' in locals() and client_file_handle:
                    client_file_handle.flush()
            except Exception as log_error:
                print(f"Warning: Failed to log error: {log_error}")

        return {
            "task_id": task_id,
            "config_id": config_id,
            "run_id": run_id,
            "status": "error",
            "error": str(e)
        }

    finally:
        # Cleanup resources based on execution mode
        print(f"[Task {task_id} | {task_label}] Cleaning up resources...")
        if 'task_logger' in locals():
            task_logger.info("=== Cleanup Phase ===")

        # Clean up remote client session
        try:
            if 'remote_client' in locals() and remote_client:
                print(f"[Task {task_id} | {task_label}] Cleaning up remote session...")
                if 'task_logger' in locals():
                    task_logger.info("Calling remote_client.cleanup()")
                remote_client.cleanup()
                if 'task_logger' in locals():
                    task_logger.info("Remote client cleanup complete")
                # Give MCP servers time to shut down gracefully
                # Increased timeout to ensure MCP servers fully exit
                time.sleep(5)
        except Exception as e:
            print(f"[Task {task_id} | {task_label}] Warning: Cleanup failed: {e}")
            if 'task_logger' in locals():
                task_logger.warning(f"Remote client cleanup failed: {e}")

        # Clean up execution mode specific resources
        if execution_mode == "sandbox" and container_name:
            # Note: Server logs are already written in real-time to temp_server_log (moved to log_dir/server.log after init)
            print(f"[Task {task_id} | {task_label}] Stopping {container_runtime} container...")
            if 'task_logger' in locals():
                task_logger.info(f"Stopping {container_runtime} container: {container_name}")
            stop_docker_container(
                container_name,
                container_runtime,
                process=container_process if 'container_process' in locals() else None,
                log_file_handle=server_log_handle if 'server_log_handle' in locals() else None
            )
            if 'task_logger' in locals():
                task_logger.info(f"{container_runtime.capitalize()} container stopped")
        elif execution_mode == "local" and server_process:
            print(f"[Task {task_id} | {task_label}] Stopping local server...")
            if 'task_logger' in locals():
                task_logger.info(f"Stopping local server process (PID {server_process.pid})")
            stop_local_server(server_process, log_file_handle=server_log_handle)
            if 'task_logger' in locals():
                task_logger.info("Local server stopped")

        # Close client log file handlers
        if 'task_logger' in locals():
            task_logger.info("Closing client log file")

            # First, remove all handlers from logger (so we can't accidentally log to closed file)
            for handler in task_logger.handlers[:]:
                try:
                    handler.flush()
                except:
                    pass
                task_logger.removeHandler(handler)

        # Now close the file handle
        if 'client_file_handle' in locals():
            try:
                client_file_handle.flush()
                client_file_handle.close()
                print(f"[Task {task_id}] Client log file closed successfully")
            except Exception as e:
                print(f"[Task {task_id}] Warning: Failed to close client log file: {e}")

        # Clean up temp client log if it still exists (error before move)
        if 'temp_client_log' in locals() and temp_client_log.exists():
            try:
                # Move to final location if possible, otherwise just note it
                if 'log_dir' in locals():
                    final_log = log_dir / "client.log"
                    if not final_log.exists():
                        import shutil
                        log_dir.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(temp_client_log), str(final_log))
                        print(f"[Task {task_id}] Temp client log moved to {final_log} during cleanup")
            except Exception as e:
                print(f"[Task {task_id}] Warning: Failed to move temp client log: {e}")
                print(f"[Task {task_id}] Temp log remains at: {temp_client_log}")

        # Close handlers after removing them
        if 'task_logger' in locals():
            for handler in list(task_logger.handlers):
                try:
                    handler.close()
                except:
                    pass


def _make_hashable(obj):
    """Convert nested dicts/lists to hashable tuples recursively."""
    if isinstance(obj, dict):
        return tuple(sorted((k, _make_hashable(v)) for k, v in obj.items()))
    elif isinstance(obj, list):
        return tuple(_make_hashable(item) for item in obj)
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        # For other types, convert to string
        return str(obj)


def normalize_config_for_grouping(config: Dict[str, Any]) -> tuple:
    """Create a normalized tuple representation of config for grouping.

    Configs that differ only by seed should map to the same tuple.
    """
    # Extract key fields for comparison
    env_class = config.get("env_class", "")
    env_params = config.get("env_params", {})
    mcp_servers = config.get("mcp_servers", {})

    # Create a frozen copy of env_params without seed
    env_params_without_seed = {k: v for k, v in env_params.items() if k != "seed"}
    env_params_tuple = _make_hashable(env_params_without_seed)

    # Create a frozen copy of mcp_servers (recursively handle nested dicts)
    mcp_servers_tuple = _make_hashable(mcp_servers)

    return (env_class, env_params_tuple, mcp_servers_tuple)


def group_configs_by_similarity(configs: List[Dict[str, Any]]) -> Dict[int, List[int]]:
    """Group configurations that differ only by seed.

    Returns:
        Dictionary mapping group_id -> list of config indices
    """
    groups = {}
    config_to_group = {}

    for i, config in enumerate(configs):
        normalized = normalize_config_for_grouping(config)

        if normalized not in config_to_group:
            # Create new group
            group_id = len(config_to_group)
            config_to_group[normalized] = group_id
            groups[group_id] = [i]
        else:
            # Add to existing group
            group_id = config_to_group[normalized]
            groups[group_id].append(i)

    return groups


def check_episode_needs_resume(episode_file: Path) -> bool:
    """Check if an episode file indicates a failed or incomplete run.

    Returns:
        True if the run needs to be resumed (failed or incomplete), False if successful
    """
    try:
        with open(episode_file, 'r') as f:
            data = json.load(f)

        # Check if the episode has a status field
        status = data.get('status')
        if status == 'error':
            return True

        # Check if final_reward indicates failure
        final_reward = data.get('final_reward', 0.0)
        accuracy = data.get('accuracy', final_reward)

        # Consider a run successful if accuracy > 0 or if it has completed steps
        if accuracy > 0 or data.get('steps', 0) > 0:
            return False

        return True
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Failed to read episode file {episode_file}: {e}")
        return True


def scan_resume_directory(resume_dir: str, delete_failed: bool = True) -> Dict[int, List[int]]:
    """Scan resume directory to find which runs need to be resumed.

    Args:
        resume_dir: Path to existing output directory
        delete_failed: If True, delete failed episode files

    Returns:
        Dictionary mapping config_id -> list of run_ids that need to be resumed
        If a config has no episode files at all, returns [-1] to indicate all runs need to be done
    """
    resume_path = Path(resume_dir)
    if not resume_path.exists():
        print(f"Error: Resume directory does not exist: {resume_dir}")
        return {}

    # Scan tasks directory
    tasks_dir = resume_path / "tasks"
    if not tasks_dir.exists():
        print(f"Error: Tasks directory not found in resume path: {tasks_dir}")
        return {}

    configs_to_resume = {}

    # Scan each config directory
    for config_dir in sorted(tasks_dir.iterdir()):
        if not config_dir.is_dir():
            continue

        config_name = config_dir.name
        # Extract config_id from directory name (assuming format like "config_0" or similar)
        # For now, use the index in sorted order
        config_id = len(configs_to_resume)

        # Scan run directories
        run_dirs = [d for d in config_dir.iterdir() if d.is_dir() and d.name.startswith("run_")]

        if not run_dirs:
            # No runs found at all, need to do all runs
            configs_to_resume[config_id] = [-1]
            continue

        failed_runs = []

        for run_dir in sorted(run_dirs):
            # Extract run_id from directory name
            try:
                run_id = int(run_dir.name.split("_")[1])
            except (IndexError, ValueError):
                print(f"Warning: Could not parse run_id from directory: {run_dir}")
                continue

            # Check for episode files
            episode_files = list(run_dir.parent.glob(f"{config_name}_run{run_id}-episode-*.json"))

            if not episode_files:
                # No episode file, needs to be resumed
                failed_runs.append(run_id)
            else:
                # Check if episode indicates failure
                episode_file = episode_files[0]  # Use first episode file
                if check_episode_needs_resume(episode_file):
                    failed_runs.append(run_id)
                    if delete_failed:
                        print(f"Deleting failed episode file: {episode_file}")
                        episode_file.unlink()

        if failed_runs:
            configs_to_resume[config_id] = sorted(failed_runs)

    return configs_to_resume


def run_config_combinations(
    config_file: str,
    runs_per_config: int = 1,
    base_task_dir: str = "",
    output_dir: str = "",
    api_key: str = "",
    base_url: str = "",
    model: str = "gpt-5-nano",
    max_tool_uses: int = 500,
    max_tokens: int = 32768,
    timeout: int = 600,
    max_workers: Optional[int] = None,
    max_retries: int = 10,
    initial_retry_delay: float = 2.0,
    reset_size: Optional[int] = None,
    reset_ratio: float = 0.5,
    context_reset: bool = False,
    context_summary: bool = False,
    context_awareness: bool = False,
    group_by_seed: bool = True,
    max_context_size: Optional[int] = None,
    memory_warning_threshold: float = 0.8,
    thinking_reset: bool = False,
    keep_thinking: int = 1,
    reasoning_effort: Optional[str] = None,
    reasoning_max_tokens: Optional[int] = None,
    reasoning_enabled: bool = True,
    reasoning_exclude: bool = False,
    resume_dir: Optional[str] = None,
    execution_mode: str = "sandbox",
    base_port: int = 9000,
    docker_image: str = "loca-bench:latest",
    container_runtime: str = "docker",
):
    """Run multiple configurations in parallel with remote environments.

    Args:
        config_file: Path to JSON configuration file
        runs_per_config: Number of runs per configuration
        base_task_dir: Base directory for task workspaces
        output_dir: Directory to save episode results
        api_key: API key (if None, will use from env)
        base_url: API base URL
        model: Model name
        max_tool_uses: Maximum tool uses per episode
        max_tokens: Maximum tokens per generation
        timeout: API request timeout
        max_workers: Maximum parallel workers
        max_retries: Maximum API retry attempts
        initial_retry_delay: Initial delay between retries in seconds
        reset_size: Token threshold for context management (None to disable all)
        reset_ratio: Ratio of tool calls to remove during reset (0.0 to 1.0)
        context_reset: If True, remove old tool calls when exceeding token limit
        context_summary: If True, generate summary when exceeding token limit
        context_awareness: If True, inform the model about token budget and usage at each step
        group_by_seed: If True, group configs that differ only by seed as same config
        max_context_size: Maximum context size in tokens (if set, will trim messages to fit)
        memory_warning_threshold: Threshold ratio (0.0-1.0) for memory warning when memory_tool is enabled
        thinking_reset: If True, clear reasoning_content from assistant messages when exceeding token limit
        keep_thinking: Number of most recent assistant messages to keep reasoning_content for (default: 1)
        reasoning_effort: The reasoning effort level for OpenAI models that support reasoning
        reasoning_max_tokens: Specific token limit for reasoning
        reasoning_enabled: Whether to enable reasoning (default: True)
        reasoning_exclude: Set to True to exclude reasoning tokens from response (default: False)
        resume_dir: Path to existing output directory to resume from
        execution_mode: Execution mode - "local" (local server) or "sandbox" (container) (default: "sandbox")
        base_port: Base port number for servers (default: 9000)
        docker_image: Container image to use for sandbox mode (default: "loca-bench:latest")
        container_runtime: Container runtime to use - "docker" or "podman" (default: "docker")
    """
    # Check for resume mode
    configs_to_resume = None
    if resume_dir:
        print(f"\n{'=' * 80}")
        print("RESUME MODE ENABLED")
        print(f"{'=' * 80}")
        print(f"Scanning resume directory: {resume_dir}")
        configs_to_resume = scan_resume_directory(resume_dir)

        if not configs_to_resume:
            print("\nNo configs need to be resumed. All runs completed successfully!")
            print(f"{'=' * 80}\n")
            return

        total_to_resume = 0
        for runs in configs_to_resume.values():
            if -1 in runs:
                total_to_resume += 1
            else:
                total_to_resume += len(runs)
        print(f"\nFound runs to resume across {len(configs_to_resume)} configs:")
        for config_id, run_ids in sorted(configs_to_resume.items()):
            if -1 in run_ids:
                print(f"  Config {config_id}: all runs (no episode files found)")
            else:
                print(f"  Config {config_id}: runs {run_ids}")
        print(f"{'=' * 80}\n")

        output_dir = resume_dir
        print(f"Resume mode: Results will be saved to: {output_dir}")
        print(f"Resume mode: Using new task workspace: {base_task_dir}")

    # Load configurations
    with open(config_file, "r") as f:
        config_data = json.load(f)

    configs = config_data.get("configurations", [])
    print(f"Loaded {len(configs)} configurations from {config_file}")

    # Group configurations if group_by_seed is enabled
    if group_by_seed:
        config_groups = group_configs_by_similarity(configs)
        print(f"\nGrouping enabled: Found {len(config_groups)} unique configuration groups")
        for group_id, config_indices in config_groups.items():
            if len(config_indices) > 1:
                print(f"  Group {group_id}: {len(config_indices)} configs with different seeds (indices: {config_indices})")
    else:
        config_groups = {i: [i] for i in range(len(configs))}
        print(f"Grouping disabled: Treating each config separately")

    # Create base directories
    Path(base_task_dir).mkdir(parents=True, exist_ok=True)
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Calculate total tasks
    if configs_to_resume is not None:
        total_tasks = 0
        for config_id, runs in configs_to_resume.items():
            if -1 in runs:
                if group_by_seed and config_id in config_groups:
                    total_tasks += max(len(config_groups[config_id]), runs_per_config)
                else:
                    total_tasks += runs_per_config
            else:
                total_tasks += len(runs)
    elif group_by_seed:
        total_tasks = sum(max(len(indices), runs_per_config) for indices in config_groups.values())
    else:
        total_tasks = len(configs) * runs_per_config

    # Set default max_workers
    if max_workers is None:
        max_workers = min(total_tasks, os.cpu_count() or 4) if total_tasks > 0 else 1

    print("=" * 80)
    print("FLEXIBLE PARALLEL INFERENCE (REMOTE MODE)")
    print("=" * 80)
    print(f"Total configurations: {len(configs)}")
    print(f"Unique config groups: {len(config_groups)}")
    print(f"Runs per configuration: {runs_per_config}")
    print(f"Total tasks: {total_tasks}")
    print(f"Max workers: {max_workers}")
    print(f"Model: {model}")
    print(f"Execution mode: {execution_mode}")
    print(f"Base port: {base_port}")
    print(f"Base task directory: {base_task_dir}")
    print(f"Output directory: {output_dir}")
    if max_context_size is not None:
        print(f"Max context size: {max_context_size:,} tokens")
    if context_awareness:
        print(f"Context awareness enabled")
    if reset_size is not None:
        if context_summary:
            print(f"Context summary enabled: reset_size={reset_size}")
        elif context_reset:
            print(f"Context reset enabled: reset_size={reset_size}, ratio={reset_ratio}")
    print("=" * 80)

    # Prepare task arguments
    task_args = []
    task_id = 0
    skipped_count = 0

    if group_by_seed:
        for group_id, config_indices in sorted(config_groups.items()):
            run_id = 0
            template_config = configs[config_indices[0]]
            total_runs_for_group = max(len(config_indices), runs_per_config)

            for i in range(total_runs_for_group):
                # Check if we should skip this run (resume mode)
                if configs_to_resume is not None:
                    if group_id not in configs_to_resume:
                        run_id += 1
                        skipped_count += 1
                        continue
                    elif -1 not in configs_to_resume[group_id] and run_id not in configs_to_resume[group_id]:
                        run_id += 1
                        skipped_count += 1
                        continue

                if i < len(config_indices):
                    config = configs[config_indices[i]]
                else:
                    config = template_config

                # Check if config provides specific reasoning settings
                config_reasoning_effort = config.get('reasoning_effort', reasoning_effort)
                config_reasoning_max_tokens = config.get('reasoning_max_tokens', reasoning_max_tokens)
                config_reasoning_enabled = config.get('reasoning_enabled', reasoning_enabled)
                config_reasoning_exclude = config.get('reasoning_exclude', reasoning_exclude)

                if config_reasoning_effort == "":
                    config_reasoning_effort = None
                if config_reasoning_max_tokens == "":
                    config_reasoning_max_tokens = None

                # Extract task name from config name
                config_name = config.get("name", f"config_{group_id}").split("-")[0]

                task_args.append((
                    task_id,
                    group_id,
                    run_id,
                    base_task_dir,
                    output_dir,
                    config_name,
                    config,
                    api_key,
                    base_url,
                    model,
                    max_tool_uses,
                    max_tokens,
                    timeout,
                    max_retries,
                    initial_retry_delay,
                    reset_size,
                    reset_ratio,
                    context_reset,
                    context_summary,
                    context_awareness,
                    max_context_size,
                    memory_warning_threshold,
                    thinking_reset,
                    keep_thinking,
                    config_reasoning_effort,
                    config_reasoning_max_tokens,
                    config_reasoning_enabled,
                    config_reasoning_exclude,
                    execution_mode,
                    base_port,
                    docker_image,
                    container_runtime,
                ))
                task_id += 1
                run_id += 1
    else:
        for config_id, config in enumerate(configs):
            for run_id in range(runs_per_config):
                # Check if we should skip this run (resume mode)
                if configs_to_resume is not None:
                    if config_id not in configs_to_resume:
                        skipped_count += 1
                        continue
                    elif -1 not in configs_to_resume[config_id] and run_id not in configs_to_resume[config_id]:
                        skipped_count += 1
                        continue

                # Check if config provides specific reasoning settings
                config_reasoning_effort = config.get('reasoning_effort', reasoning_effort)
                config_reasoning_max_tokens = config.get('reasoning_max_tokens', reasoning_max_tokens)
                config_reasoning_enabled = config.get('reasoning_enabled', reasoning_enabled)
                config_reasoning_exclude = config.get('reasoning_exclude', reasoning_exclude)

                if config_reasoning_effort == "":
                    config_reasoning_effort = None
                if config_reasoning_max_tokens == "":
                    config_reasoning_max_tokens = None

                config_name = config.get("name", f"config_{config_id}").split("-")[0]

                task_args.append((
                    task_id,
                    config_id,
                    run_id,
                    base_task_dir,
                    output_dir,
                    config_name,
                    config,
                    api_key,
                    base_url,
                    model,
                    max_tool_uses,
                    max_tokens,
                    timeout,
                    max_retries,
                    initial_retry_delay,
                    reset_size,
                    reset_ratio,
                    context_reset,
                    context_summary,
                    context_awareness,
                    max_context_size,
                    memory_warning_threshold,
                    thinking_reset,
                    keep_thinking,
                    config_reasoning_effort,
                    config_reasoning_max_tokens,
                    config_reasoning_enabled,
                    config_reasoning_exclude,
                    execution_mode,
                    base_port,
                    docker_image,
                    container_runtime,
                ))
                task_id += 1

    # Print resume mode summary
    if configs_to_resume is not None:
        print(f"Resume mode: {skipped_count} runs skipped, {len(task_args)} runs to execute")

    # Check if there are any tasks to run
    if not task_args:
        print("\nNo tasks to run. All runs completed successfully!")
        return

    # Run tasks in parallel
    start_time = time.time()
    results = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(run_single_task, *args): (args[0], args[1], args[2])
            for args in task_args
        }

        # Collect results as they complete
        for future in as_completed(futures):
            task_id, config_id, run_id = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(f"\n{'=' * 80}")
                print(f"Task {task_id} (Config {config_id}, Run {run_id}) finished: {result['status']}")
                if result['status'] == 'success':
                    print(f"  Steps: {result['steps']}, Accuracy: {result.get('accuracy', result['final_reward'])}")
                print(f"{'=' * 80}\n")
            except Exception as e:
                print(f"\n{'=' * 80}")
                print(f"Task {task_id} (Config {config_id}, Run {run_id}) raised an exception: {e}")
                print(f"{'=' * 80}\n")
                results.append({
                    "task_id": task_id,
                    "config_id": config_id,
                    "run_id": run_id,
                    "status": "exception",
                    "error": str(e),
                })

    elapsed_time = time.time() - start_time

    # Analyze results
    config_stats = {}
    for result in results:
        config_id = result.get("config_id", 0)
        if config_id not in config_stats:
            config_stats[config_id] = {
                "total": 0,
                "success": 0,
                "error": 0,
                "accuracies": [],
                "steps": [],
            }

        config_stats[config_id]["total"] += 1
        if result["status"] == "success":
            config_stats[config_id]["success"] += 1
            accuracy = result.get("accuracy", result["final_reward"])
            config_stats[config_id]["accuracies"].append(accuracy)
            config_stats[config_id]["steps"].append(result["steps"])
        else:
            config_stats[config_id]["error"] += 1

    # Print summary
    print("\n" + "=" * 80)
    if resume_dir:
        print("PARALLEL INFERENCE SUMMARY (RESUME MODE)")
    else:
        print("PARALLEL INFERENCE SUMMARY (REMOTE MODE)")
    print("=" * 80)
    if resume_dir:
        print(f"Resume directory: {resume_dir}")
    print(f"Total time: {elapsed_time:.2f} seconds")
    print(f"Total tasks completed: {len(results)}")
    print(f"\nPer-configuration results:")

    for config_id in sorted(config_stats.keys()):
        stats = config_stats[config_id]
        print(f"\n  Config {config_id}:")
        print(f"    Total runs: {stats['total']}")
        print(f"    Successful: {stats['success']}")
        print(f"    Failed: {stats['error']}")

        if stats['accuracies']:
            avg_accuracy = sum(stats['accuracies']) / len(stats['accuracies'])
            avg_steps = sum(stats['steps']) / len(stats['steps'])
            print(f"    Average accuracy: {avg_accuracy:.3f}")
            print(f"    Average steps: {avg_steps:.1f}")

    print("=" * 80 + "\n")


def main():
    """Main entry point."""
    fire.Fire(run_config_combinations)


if __name__ == "__main__":
    main()
