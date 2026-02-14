"""Environment session management for remote execution."""

import json
import logging
import uuid
from pathlib import Path
from typing import Dict, List

from gem.tools.mcp_tool import MCPTool
from gem.tools.tool_env_wrapper import ToolEnvWrapperOpenAI
from gem.utils.dynamic_import import dynamic_import_class


logger = logging.getLogger(__name__)


class EnvironmentSession:
    """Manages a single environment instance with MCP servers."""

    def __init__(self, config: Dict, task_workspace: Path, agent_workspace: Path):
        """
        Initialize environment session.

        Args:
            config: Task configuration dictionary
            task_workspace: Path to task workspace directory
            agent_workspace: Path to agent workspace directory
        """
        self.session_id = str(uuid.uuid4())
        self.config = config
        self.task_workspace = Path(task_workspace)
        self.agent_workspace = Path(agent_workspace)

        # Create workspace directories
        self.task_workspace.mkdir(parents=True, exist_ok=True)
        self.agent_workspace.mkdir(parents=True, exist_ok=True)

        # Initialize environment
        self.env = None
        self.tool_wrapper = None
        self.mcp_tool = None
        self.tools = []
        self.initial_observation = None
        self.initial_info = None

        self._setup_environment()

    def _setup_environment(self):
        """Setup environment, MCP servers, and tool wrappers."""
        import os as _os
        import shutil as _shutil
        logger.info(f"[DEBUG] Server process PATH: {_os.environ.get('PATH', 'NOT SET')}")
        for _bin in ["npx", "node", "python", "excel-mcp-server"]:
            logger.info(f"[DEBUG] which {_bin}: {_shutil.which(_bin)}")
        try:
            # Import and instantiate environment class
            env_class = dynamic_import_class(self.config["env_class"])
            env_params = self.config.get("env_params", {}).copy()

            # Prepare environment parameters with path replacements
            prepared_env_params = {}
            for key, value in env_params.items():
                if isinstance(value, str):
                    value = value.replace("{task_workspace}", str(self.task_workspace))
                    value = value.replace("{agent_workspace}", str(self.agent_workspace))
                prepared_env_params[key] = value

            # Add task_dir if not specified
            if "task_dir" not in prepared_env_params:
                prepared_env_params["task_dir"] = str(self.task_workspace)

            # Extract seed for reset call
            if "seed" in prepared_env_params:
                seed = prepared_env_params["seed"]
            else:
                seed = None

            self.env = env_class(**prepared_env_params)
            logger.info(f"Session {self.session_id}: Created environment {self.config['env_class']}")

            # Setup MCP servers
            mcp_servers = self.config.get("mcp_servers", {})
            if mcp_servers:
                mcp_config = self._setup_mcp_servers(mcp_servers)
                # Log the full config so we can see exactly what commands/env are used
                import json as _json
                import time as _time
                for srv_name, srv_cfg in mcp_config.get("mcpServers", {}).items():
                    _cmd = srv_cfg.get("command", "?")
                    _args = srv_cfg.get("args", [])
                    _env = srv_cfg.get("env", {})
                    logger.info(
                        f"Session {self.session_id}: MCP server '{srv_name}': "
                        f"command={_cmd}, args={_args}, env={_json.dumps(_env) if _env else 'inherited'}"
                    )
                logger.info(f"Session {self.session_id}: >>> Creating MCPTool with {len(mcp_config.get('mcpServers', {}))} servers (this triggers tool discovery)...")
                _t0 = _time.time()
                self.mcp_tool = MCPTool(mcp_config, execution_timeout=120.0)
                _elapsed = _time.time() - _t0
                logger.info(f"Session {self.session_id}: <<< MCPTool created in {_elapsed:.1f}s, {len(mcp_config.get('mcpServers', {}))} MCP servers initialized")

            # Wrap environment with tool support
            # Use max_tool_uses=10000 to match the default in run_react.py
            tools = [self.mcp_tool] if self.mcp_tool else []
            self.tool_wrapper = ToolEnvWrapperOpenAI(self.env, tools=tools, max_tool_uses=10000)

            # Use stored reset result from env.__init__() — no second env.reset()
            obs, info = self.env._last_reset_result
            obs, info, user_prompt, tool_schemas = self.tool_wrapper.initialize(obs, info)

            # Store the results
            self.initial_observation = user_prompt  # Use user_prompt as the initial observation
            self.initial_info = info

            # Flatten tool schemas (tool_schemas is a list of lists, one per tool wrapper)
            self.tools = []
            for tool_list in tool_schemas:
                if isinstance(tool_list, list):
                    self.tools.extend(tool_list)
                else:
                    self.tools.append(tool_list)

            logger.info(f"Session {self.session_id}: Loaded {len(self.tools)} tools")

            logger.info(f"Session {self.session_id}: Environment reset complete")

        except Exception as e:
            logger.error(f"Session {self.session_id}: Failed to setup environment: {e}", exc_info=True)
            raise

    def _setup_mcp_servers(self, mcp_servers_config: Dict) -> Dict:
        """
        Setup MCP servers from configuration.

        Args:
            mcp_servers_config: MCP server configuration dictionary

        Returns:
            Dictionary with mcpServers configuration for MCPTool
        """
        from gem.tools.mcp_server.config_loader import build_server_config

        config = {"mcpServers": {}}

        for server_name, server_config in mcp_servers_config.items():
            if not server_config.get("enabled", True):
                continue

            server_type = server_config.get("type", server_name)
            params = server_config.get("params", {})

            # Replace workspace placeholders
            params_str = json.dumps(params)
            params_str = params_str.replace("{task_workspace}", str(self.task_workspace))
            params_str = params_str.replace("{agent_workspace}", str(self.agent_workspace))
            params = json.loads(params_str)

            # Add workspace paths to params for placeholder replacement in YAML loader
            params["task_workspace"] = str(self.task_workspace)
            params["agent_workspace"] = str(self.agent_workspace)

            # Use YAML-based config loader (same as run_react.py)
            server_cfg = build_server_config(
                server_type=server_type,
                params=params,
                server_name=server_name
            )

            config["mcpServers"].update(server_cfg)
            logger.debug(f"Session {self.session_id}: Configured MCP server {server_name} ({server_type})")

        return config

    def get_initial_state(self) -> Dict:
        """
        Get initial state for client.

        Returns:
            Dictionary with session_id, observation, info, and tools
        """
        return {
            "session_id": self.session_id,
            "observation": self.initial_observation,
            "info": self.initial_info or {},
            "tools": self.tools
        }

    def execute_tool(self, tool_name: str, arguments: Dict, tool_call_id: str) -> Dict:
        """
        Execute a tool call.

        Args:
            tool_name: Name of the tool to execute
            arguments: Tool arguments
            tool_call_id: Unique identifier for this tool call

        Returns:
            Dictionary with tool execution result
        """
        try:
            logger.debug(f"Session {self.session_id}: Executing tool {tool_name} with args {arguments}")

            # Create tool call format expected by step_openai
            tool_call = {
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": json.dumps(arguments)
                }
            }

            # Execute via tool wrapper
            # step_openai expects a response dict with type="tool" and data=[tool_calls]
            response = {
                "type": "tool",
                "data": [tool_call]
            }

            # Execute tool and get result
            logger.info(f"Session {self.session_id}: ========================================")
            logger.info(f"Session {self.session_id}: EXECUTING TOOL: {tool_name}")
            logger.info(f"Session {self.session_id}: Arguments: {arguments}")
            logger.info(f"Session {self.session_id}: Tool call ID: {tool_call_id}")
            logger.info(f"Session {self.session_id}: Request to step_openai: {response}")

            obs, _reward, _terminated, _truncated, info = self.tool_wrapper.step_openai(response, verbose=True)

            logger.info(f"Session {self.session_id}: Tool execution completed")
            logger.info(f"Session {self.session_id}: obs type: {type(obs)}, length: {len(obs)}")
            logger.info(f"Session {self.session_id}: obs content: {obs}")
            logger.info(f"Session {self.session_id}: reward: {_reward}, terminated: {_terminated}, truncated: {_truncated}")
            logger.info(f"Session {self.session_id}: info: {info}")
            logger.info(f"Session {self.session_id}: ========================================")

            # Parse tool results from observation
            # obs is a JSON string containing an array of tool results
            error = None
            try:
                logger.info(f"Session {self.session_id}: Parsing obs as JSON...")
                tool_results = json.loads(obs)
                logger.info(f"Session {self.session_id}: Parsed tool_results: type={type(tool_results)}, len={len(tool_results) if isinstance(tool_results, list) else 'N/A'}")

                if isinstance(tool_results, list) and len(tool_results) > 0:
                    # Extract the content from the first tool result
                    tool_result = tool_results[0]
                    logger.info(f"Session {self.session_id}: First tool_result keys: {tool_result.keys()}")
                    content = tool_result.get("content", "")
                    logger.info(f"Session {self.session_id}: Extracted content: {content[:200] if len(content) > 200 else content}")

                    # Check if tool execution actually succeeded
                    # NOTE: Empty arrays/objects like "[]" or "{}" are VALID results, not errors
                    if "not found" in content.lower() and "tool" in content.lower():
                        success = False
                        error = f"Tool not found: {tool_name}"
                        logger.info(f"Session {self.session_id}: Tool not found error detected")
                    elif "error" in content.lower() and len(content) > 10:
                        # Only treat as error if it looks like an error message (not just empty array)
                        success = False
                        error = content
                        logger.info(f"Session {self.session_id}: Error content detected")
                    else:
                        # Tool executed successfully (even if result is empty array/object)
                        success = True
                        logger.info(f"Session {self.session_id}: Tool executed successfully")

                    logger.info(f"Session {self.session_id}: Final result - content length: {len(content)}, success: {success}")
                else:
                    # Empty tool results array - tool didn't execute at all
                    error = f"Tool '{tool_name}' did not execute - step_openai returned empty tool results array"
                    content = error
                    success = False
                    logger.warning(f"Session {self.session_id}: ❌ Empty tool results array for {tool_name}!")
                    logger.warning(f"Session {self.session_id}: Raw obs: {obs}")
                    logger.warning(f"Session {self.session_id}: Tool call sent: {tool_call}")
                    logger.warning(f"Session {self.session_id}: Info from step_openai: {info}")
            except (json.JSONDecodeError, KeyError) as e:
                # If parsing fails, use obs as-is
                content = obs
                success = False
                error = f"Failed to parse tool results: {str(e)}"
                logger.warning(f"Session {self.session_id}: ❌ Failed to parse tool results: {e}")

            result = {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": content,
                "success": success,
                "error": error
            }

            logger.debug(f"Session {self.session_id}: Tool {tool_name} execution complete, success={success}")
            return result

        except Exception as e:
            logger.error(f"Session {self.session_id}: Tool execution failed: {e}", exc_info=True)
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": f"Error executing tool: {str(e)}",
                "success": False,
                "error": str(e)
            }

    def evaluate(self, action: str = "claim_done") -> Dict:
        """
        Evaluate task completion.

        Args:
            action: Action string for evaluation (default: "claim_done")

        Returns:
            Dictionary with evaluation results
        """
        try:
            logger.info(f"Session {self.session_id}: Evaluating with action '{action}'")

            # CRITICAL: Close MCP tool database connections BEFORE evaluation
            # Evaluation opens its own connection, and multiple connections can't see
            # each other's changes properly even with WAL checkpointing
            if self.mcp_tool:
                logger.info(f"Session {self.session_id}: Closing MCP database connections before evaluation")
                try:
                    self.mcp_tool.close()
                    logger.info(f"Session {self.session_id}: MCP connections closed")
                except Exception as e:
                    logger.warning(f"Session {self.session_id}: Failed to close MCP tool: {e}")

            # Call step on wrapped environment
            observation, reward, terminated, truncated, info = self.tool_wrapper.step(action)

            result = {
                "observation": observation,
                "reward": float(reward),
                "terminated": bool(terminated),
                "truncated": bool(truncated),
                "info": info or {}
            }

            logger.info(f"Session {self.session_id}: Evaluation complete - reward={reward}, terminated={terminated}")
            return result

        except Exception as e:
            logger.error(f"Session {self.session_id}: Evaluation failed: {e}", exc_info=True)
            return {
                "observation": f"Evaluation error: {str(e)}",
                "reward": 0.0,
                "terminated": True,
                "truncated": False,
                "info": {"error": str(e)}
            }

    def cleanup(self):
        """Clean up session resources."""
        try:
            logger.info(f"Session {self.session_id}: Cleaning up resources")

            # Cleanup MCP tool (stops MCP servers)
            if self.mcp_tool:
                try:
                    self.mcp_tool.close()
                    logger.info(f"Session {self.session_id}: MCP tool closed successfully")
                except Exception as e:
                    logger.warning(f"Session {self.session_id}: MCP tool cleanup failed: {e}")

            # Cleanup environment
            if self.env:
                try:
                    # Call environment cleanup if available
                    if hasattr(self.env, "close"):
                        self.env.close()
                    elif hasattr(self.env, "cleanup"):
                        self.env.cleanup()
                except Exception as e:
                    logger.warning(f"Session {self.session_id}: Environment cleanup failed: {e}")

            logger.info(f"Session {self.session_id}: Cleanup complete")

        except Exception as e:
            logger.error(f"Session {self.session_id}: Cleanup error: {e}", exc_info=True)

    def __del__(self):
        """Destructor to ensure cleanup."""
        self.cleanup()
