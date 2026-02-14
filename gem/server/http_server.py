"""HTTP server for remote environment execution."""

import argparse
import atexit
import logging
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from gem.server.environment_session import EnvironmentSession


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Global session storage
sessions: Dict[str, EnvironmentSession] = {}
session_lock = threading.Lock()

def cleanup_all_sessions():
    """Clean up all active sessions (called on shutdown)."""
    logger.info("Cleaning up all active sessions...")
    with session_lock:
        session_ids = list(sessions.keys())

    for session_id in session_ids:
        try:
            with session_lock:
                session = sessions.pop(session_id, None)
            if session:
                session.cleanup()
                logger.info(f"Cleaned up session {session_id}")
        except Exception as e:
            logger.error(f"Failed to cleanup session {session_id}: {e}")

    logger.info("All sessions cleaned up")

def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down...")
    cleanup_all_sessions()
    sys.exit(0)

# Register cleanup handlers
atexit.register(cleanup_all_sessions)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


# Request/Response models
class InitRequest(BaseModel):
    task_name: str
    config: Dict
    task_workspace: str
    agent_workspace: str


class InitResponse(BaseModel):
    session_id: str
    observation: str
    info: Dict
    tools: list


class ToolExecutionRequest(BaseModel):
    session_id: str
    tool_name: str
    arguments: Dict
    tool_call_id: str


class ToolExecutionResponse(BaseModel):
    role: str
    tool_call_id: str
    content: str
    success: bool
    error: Optional[str] = None


class EvaluationRequest(BaseModel):
    session_id: str
    action: str = "claim_done"


class EvaluationResponse(BaseModel):
    observation: str
    reward: float
    terminated: bool
    truncated: bool
    info: Dict


class CleanupRequest(BaseModel):
    session_id: str


class CleanupResponse(BaseModel):
    success: bool


class HealthResponse(BaseModel):
    status: str
    active_sessions: int


# Create FastAPI app
app = FastAPI(
    title="LOCA-bench Remote Environment Server",
    description="HTTP server for remote environment execution",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Shutdown event handler to clean up all sessions
@app.on_event("shutdown")
def shutdown_event():
    """Clean up all active sessions on server shutdown."""
    logger.info("FastAPI shutdown event triggered")
    cleanup_all_sessions()


@app.get("/api/v1/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    with session_lock:
        active_sessions = len(sessions)
    logger.debug(f"[HEALTH] Health check - active sessions: {active_sessions}")
    return {
        "status": "ok",
        "active_sessions": active_sessions
    }


@app.post("/api/v1/init", response_model=InitResponse)
def initialize_environment(request: InitRequest):
    """
    Initialize environment for a task.

    Creates a new session with environment and MCP servers.
    """
    logger.info("="*80)
    logger.info("[INIT] Received initialization request")
    logger.info(f"[INIT] Task: {request.task_name}")
    logger.info(f"[INIT] Config: {request.config.get('name', 'unknown')}")
    logger.info(f"[INIT] Task workspace: {request.task_workspace}")
    logger.info(f"[INIT] Agent workspace: {request.agent_workspace}")
    logger.info("="*80)

    try:
        # Create session
        logger.info("[INIT] Creating EnvironmentSession...")
        session = EnvironmentSession(
            config=request.config,
            task_workspace=Path(request.task_workspace),
            agent_workspace=Path(request.agent_workspace)
        )

        # Store session
        with session_lock:
            sessions[session.session_id] = session

        # Get initial state
        initial_state = session.get_initial_state()

        logger.info(f"[INIT] ✓ Session created: {session.session_id}")
        logger.info(f"[INIT] ✓ Tools loaded: {len(initial_state['tools'])}")
        logger.info(f"[INIT] ✓ Observation length: {len(initial_state['observation'])} chars")
        logger.info("="*80)

        return InitResponse(**initial_state)

    except Exception as e:
        import traceback
        logger.error("[INIT] ✗ ERROR: Failed to initialize environment")
        logger.error(f"[INIT] Error: {str(e)}")
        logger.error(f"[INIT] Traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize environment: {str(e)}")


@app.post("/api/v1/execute_tool", response_model=ToolExecutionResponse)
def execute_tool(request: ToolExecutionRequest):
    """
    Execute a tool call.

    Executes the specified tool in the session's environment.
    """
    logger.info("-"*80)
    logger.info(f"[TOOL] Executing tool: {request.tool_name}")
    logger.info(f"[TOOL] Session: {request.session_id[:8]}...")
    logger.info(f"[TOOL] Tool call ID: {request.tool_call_id}")
    logger.info(f"[TOOL] Arguments: {request.arguments}")

    try:
        # Get session
        with session_lock:
            session = sessions.get(request.session_id)

        if not session:
            logger.error(f"[TOOL] ✗ Session not found: {request.session_id}")
            raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found")

        # Execute tool
        result = session.execute_tool(
            tool_name=request.tool_name,
            arguments=request.arguments,
            tool_call_id=request.tool_call_id
        )

        logger.info(f"[TOOL] ✓ Tool executed: {request.tool_name}")
        logger.info(f"[TOOL] Success: {result.get('success', False)}")
        logger.info(f"[TOOL] Content length: {len(str(result.get('content', '')))} chars")
        if result.get('error'):
            logger.warning(f"[TOOL] Error: {result.get('error')}")
        logger.info("-"*80)

        return ToolExecutionResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"[TOOL] ✗ Failed to execute tool: {request.tool_name}")
        logger.error(f"[TOOL] Error: {str(e)}")
        logger.error(f"[TOOL] Traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to execute tool: {str(e)}")


@app.post("/api/v1/evaluate", response_model=EvaluationResponse)
def evaluate_task(request: EvaluationRequest):
    """
    Evaluate task completion.

    Runs evaluation on the session's environment.
    """
    logger.info("="*80)
    logger.info(f"[EVAL] Evaluating task")
    logger.info(f"[EVAL] Session: {request.session_id[:8]}...")
    logger.info(f"[EVAL] Action: {request.action}")
    logger.info("="*80)

    try:
        # Get session
        with session_lock:
            session = sessions.get(request.session_id)

        if not session:
            logger.error(f"[EVAL] ✗ Session not found: {request.session_id}")
            raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found")

        # Evaluate
        result = session.evaluate(action=request.action)

        logger.info(f"[EVAL] ✓ Evaluation complete")
        logger.info(f"[EVAL] Reward: {result.get('reward', 0.0)}")
        logger.info(f"[EVAL] Terminated: {result.get('terminated', False)}")
        logger.info(f"[EVAL] Truncated: {result.get('truncated', False)}")
        logger.info(f"[EVAL] Info: {result.get('info', {})}")
        logger.info("="*80)

        return EvaluationResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"[EVAL] ✗ Failed to evaluate task")
        logger.error(f"[EVAL] Error: {str(e)}")
        logger.error(f"[EVAL] Traceback:\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to evaluate task: {str(e)}")


@app.post("/api/v1/cleanup", response_model=CleanupResponse)
def cleanup_session(request: CleanupRequest):
    """
    Clean up session resources.

    Stops MCP servers and removes session from storage.
    """
    logger.info("="*80)
    logger.info(f"[CLEANUP] Cleaning up session")
    logger.info(f"[CLEANUP] Session: {request.session_id[:8]}...")
    logger.info("="*80)

    try:
        # Get and remove session
        with session_lock:
            session = sessions.pop(request.session_id, None)

        if not session:
            logger.warning(f"[CLEANUP] ⚠ Session not found: {request.session_id}")
            return {"success": False}

        # Cleanup session
        logger.info(f"[CLEANUP] Stopping MCP servers...")
        session.cleanup()

        logger.info(f"[CLEANUP] ✓ Session cleaned up successfully")
        logger.info(f"[CLEANUP] Remaining sessions: {len(sessions)}")
        logger.info("="*80)
        return {"success": True}

    except Exception as e:
        import traceback
        logger.error(f"[CLEANUP] ✗ Failed to cleanup session")
        logger.error(f"[CLEANUP] Error: {str(e)}")
        logger.error(f"[CLEANUP] Traceback:\n{traceback.format_exc()}")
        return {"success": False}


def main():
    """Main entry point for server."""
    parser = argparse.ArgumentParser(description="LOCA-bench Remote Environment Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--workspace-base", type=str, default="/workspace/outputs", help="Base workspace directory")
    parser.add_argument("--log-level", type=str, default="INFO", help="Logging level")
    args = parser.parse_args()

    # Configure logging to stdout only
    # The client will redirect stdout to a file for logging
    log_level = getattr(logging, args.log_level.upper())
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers
    root_logger.handlers.clear()

    # Add stdout handler with unbuffered output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)

    # Force flush after each log
    sys.stdout.reconfigure(line_buffering=True)

    logging.info(f"Server starting on {args.host}:{args.port}")
    logging.info(f"Log level: {args.log_level}")
    logging.info(f"Workspace base: {args.workspace_base}")

    # Create workspace directory
    workspace_base = Path(args.workspace_base)
    workspace_base.mkdir(parents=True, exist_ok=True)

    logger.info(f"Starting server on {args.host}:{args.port}")
    logger.info(f"Workspace base: {workspace_base}")
    logger.info("="*80)

    # Run server - don't pass log_config to let it use our custom logging
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level.lower(),
        log_config=None  # Use default/existing logging configuration
    )


if __name__ == "__main__":
    main()
