"""Remote environment client for communicating with HTTP server."""

import json
import logging
import time
from typing import Dict, List, Optional, Tuple

import requests


logger = logging.getLogger(__name__)


class RemoteEnvironmentClient:
    """Client that communicates with remote environment server."""

    def __init__(self, server_url: str, config: Dict, task_workspace: str, agent_workspace: str, timeout: int = 300):
        """
        Initialize remote environment client.

        Args:
            server_url: Base URL of the remote server (e.g., http://localhost:9000)
            config: Task configuration dictionary
            task_workspace: Path to task workspace directory
            agent_workspace: Path to agent workspace directory
            timeout: Default timeout for requests in seconds
        """
        self.server_url = server_url.rstrip("/")
        self.config = config
        self.task_workspace = task_workspace
        self.agent_workspace = agent_workspace
        self.timeout = timeout
        self.session_id = None
        self.tools = None

    def wait_for_server(self, max_retries: int = 30, retry_interval: float = 1.0) -> bool:
        """
        Wait for server to become available.

        Args:
            max_retries: Maximum number of retry attempts
            retry_interval: Time to wait between retries in seconds

        Returns:
            True if server is available, False otherwise
        """
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    f"{self.server_url}/api/v1/health",
                    timeout=5
                )
                if response.status_code == 200:
                    logger.info(f"Server at {self.server_url} is ready")
                    return True
            except requests.exceptions.RequestException:
                pass

            if attempt < max_retries - 1:
                logger.debug(f"Waiting for server (attempt {attempt + 1}/{max_retries})...")
                time.sleep(retry_interval)

        logger.error(f"Server at {self.server_url} did not become available")
        return False

    def reset(self) -> Tuple[str, Dict]:
        """
        Initialize remote environment.

        Returns:
            Tuple of (observation, info)
        """
        try:
            logger.info(f"Initializing remote environment for task: {self.config['name']}")

            response = requests.post(
                f"{self.server_url}/api/v1/init",
                json={
                    "task_name": self.config["name"],
                    "config": self.config,
                    "task_workspace": self.task_workspace,
                    "agent_workspace": self.agent_workspace
                },
                timeout=self.timeout
            )

            response.raise_for_status()
            data = response.json()

            self.session_id = data["session_id"]
            self.tools = data["tools"]

            logger.info(f"Remote environment initialized with session {self.session_id}")
            logger.debug(f"Available tools: {[t['function']['name'] for t in self.tools]}")

            return data["observation"], data["info"]

        except requests.exceptions.Timeout as e:
            task_name = self.config.get("name", "unknown")
            logger.error(f"⏱️  Timeout during initialization for task '{task_name}': environment setup took longer than {self.timeout} seconds")
            raise RuntimeError(
                f"⏱️  Timeout: Task '{task_name}' initialization exceeded {self.timeout}s timeout. "
                f"The environment's reset() method (preprocessing) is taking too long. "
                f"This could indicate a complex environment or a hanging process."
            ) from e

        except requests.exceptions.RequestException as e:
            task_name = self.config.get("name", "unknown")
            logger.error(f"Failed to initialize remote environment for task '{task_name}': {e}")

            # Try to get error details from response if available
            error_details = ""
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details = f"\nServer response: {e.response.text[:500]}"
                except:
                    pass

            raise RuntimeError(f"Failed to initialize remote environment for task '{task_name}': {e}{error_details}") from e

    def execute_tool(self, tool_name: str, arguments: Dict, tool_call_id: str) -> Dict:
        """
        Execute tool on remote server.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            tool_call_id: Unique identifier for this tool call

        Returns:
            Dictionary with tool execution result
        """
        if not self.session_id:
            raise RuntimeError("Session not initialized. Call reset() first.")

        try:
            logger.debug(f"Executing remote tool: {tool_name}")

            response = requests.post(
                f"{self.server_url}/api/v1/execute_tool",
                json={
                    "session_id": self.session_id,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "tool_call_id": tool_call_id
                },
                timeout=120
            )

            response.raise_for_status()
            result = response.json()

            if not result.get("success", True):
                logger.warning(f"Tool execution failed: {result.get('error', 'Unknown error')}")

            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to execute remote tool: {e}")
            # Return error result instead of raising
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": f"Error executing remote tool: {str(e)}",
                "success": False,
                "error": str(e)
            }

    def execute_tools(self, tool_calls: List[Dict]) -> List[Dict]:
        """
        Execute multiple tool calls.

        Args:
            tool_calls: List of tool call dictionaries

        Returns:
            List of tool execution results
        """
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"])
            tool_call_id = tool_call["id"]

            result = self.execute_tool(tool_name, arguments, tool_call_id)
            results.append(result)

        return results

    def evaluate(self, action: str = "claim_done") -> Tuple[str, float, bool, bool, Dict]:
        """
        Evaluate task completion on remote server.

        Args:
            action: Action string for evaluation (default: "claim_done")

        Returns:
            Tuple of (observation, reward, terminated, truncated, info)
        """
        if not self.session_id:
            raise RuntimeError("Session not initialized. Call reset() first.")

        try:
            logger.info("Evaluating task completion")

            response = requests.post(
                f"{self.server_url}/api/v1/evaluate",
                json={
                    "session_id": self.session_id,
                    "action": action
                },
                timeout=60
            )

            response.raise_for_status()
            data = response.json()

            logger.info(f"Evaluation complete - reward={data['reward']}, terminated={data['terminated']}")

            return (
                data["observation"],
                data["reward"],
                data["terminated"],
                data["truncated"],
                data["info"]
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to evaluate task: {e}")
            raise RuntimeError(f"Failed to evaluate task: {e}") from e

    def cleanup(self):
        """Clean up remote session."""
        if not self.session_id:
            return

        try:
            logger.info(f"Cleaning up remote session {self.session_id}")

            response = requests.post(
                f"{self.server_url}/api/v1/cleanup",
                json={"session_id": self.session_id},
                timeout=30
            )

            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                logger.info("Remote session cleaned up successfully")
            else:
                logger.warning("Remote session cleanup reported failure")

        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to cleanup remote session: {e}")
        finally:
            self.session_id = None
            self.tools = None

    def get_tools(self) -> List[Dict]:
        """
        Get available tools.

        Returns:
            List of tool schemas in OpenAI format
        """
        if not self.tools:
            raise RuntimeError("Session not initialized. Call reset() first.")
        return self.tools

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
