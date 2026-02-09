# Copyright 2025 LOCA-bench Contributors. All Rights Reserved.
#
# Licensed under the MIT License.

"""Output directory construction utilities for LOCA-bench CLI."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from loca.cli.utils.config_resolver import PROJECT_ROOT, Strategy


def sanitize_model_name(model: str) -> str:
    """Sanitize model name for use in file/directory paths.

    Replaces forward slashes with hyphens.

    Args:
        model: Model name (e.g., "openai/gpt-4").

    Returns:
        Sanitized model name (e.g., "openai-gpt-4").
    """
    return model.replace("/", "-")


def build_param_suffix(
    context_reset: bool,
    context_summary: bool,
    context_awareness: bool,
    thinking_reset: bool,
    reset_size: int,
    reset_ratio: float,
    max_context_size: int,
    memory_warning_threshold: float,
    keep_thinking: int,
    reasoning_effort: Optional[str],
    reasoning_max_tokens: Optional[int],
) -> str:
    """Build parameter suffix for output directory name.

    Args:
        context_reset: Whether context reset is enabled.
        context_summary: Whether context summary is enabled.
        context_awareness: Whether context awareness is enabled.
        thinking_reset: Whether thinking reset is enabled.
        reset_size: Token threshold for reset.
        reset_ratio: Ratio of context to keep after reset.
        max_context_size: Maximum context size.
        memory_warning_threshold: Memory warning threshold.
        keep_thinking: Number of thinking traces to keep.
        reasoning_effort: Reasoning effort level.
        reasoning_max_tokens: Reasoning max tokens.

    Returns:
        Parameter suffix string (e.g., "_CR_CS_RS200000_RR0.5_MC128000_MW0.5").
    """
    suffix = ""

    # Feature flags
    if context_reset:
        suffix += "_CR"
    if context_summary:
        suffix += "_CS"
    if context_awareness:
        suffix += "_CA"
    if thinking_reset:
        suffix += "_TR"

    # Always add these parameters
    suffix += f"_RS{reset_size}_RR{reset_ratio}_MC{max_context_size}_MW{memory_warning_threshold}"

    # Conditional parameters
    if thinking_reset:
        suffix += f"_KT{keep_thinking}"

    if reasoning_effort:
        suffix += f"_RE{reasoning_effort}"
    elif reasoning_max_tokens:
        suffix += f"_RT{reasoning_max_tokens}"

    return suffix


def build_output_dir(
    config_file: str,
    strategy: Strategy,
    model: str,
    context_reset: bool = False,
    context_summary: bool = False,
    context_awareness: bool = False,
    thinking_reset: bool = False,
    reset_size: int = 200000,
    reset_ratio: float = 0.5,
    max_context_size: int = 128000,
    memory_warning_threshold: float = 0.5,
    keep_thinking: int = 1,
    reasoning_effort: Optional[str] = None,
    reasoning_max_tokens: Optional[int] = None,
    resume_dir: Optional[str] = None,
    add_timestamp: bool = True,
) -> Path:
    """Build the output directory path for benchmark results.

    Args:
        config_file: Config filename (basename extracted).
        strategy: The context management strategy.
        model: Model name.
        context_reset: Whether context reset is enabled.
        context_summary: Whether context summary is enabled.
        context_awareness: Whether context awareness is enabled.
        thinking_reset: Whether thinking reset is enabled.
        reset_size: Token threshold for reset.
        reset_ratio: Ratio of context to keep after reset.
        max_context_size: Maximum context size.
        memory_warning_threshold: Memory warning threshold.
        keep_thinking: Number of thinking traces to keep.
        reasoning_effort: Reasoning effort level.
        reasoning_max_tokens: Reasoning max tokens.
        resume_dir: Optional path to resume from. If "true", auto-construct path.
        add_timestamp: Whether to add timestamp to directory name.

    Returns:
        Path to output directory.

    Raises:
        FileNotFoundError: If resume_dir is specified but doesn't exist.
    """
    # Handle resume mode
    if resume_dir:
        if resume_dir.lower() == "true":
            # Auto-construct resume path (no timestamp)
            pass  # Fall through to build path without timestamp
        else:
            # Use provided path directly
            output_path = Path(resume_dir)
            if not output_path.is_dir():
                raise FileNotFoundError(
                    f"Resume directory does not exist: {output_path}"
                )
            return output_path
        add_timestamp = False

    # Extract config basename (without path and extension)
    config_basename = Path(config_file).stem

    # Sanitize model name
    model_safe = sanitize_model_name(model)

    # Build parameter suffix
    param_suffix = build_param_suffix(
        context_reset=context_reset,
        context_summary=context_summary,
        context_awareness=context_awareness,
        thinking_reset=thinking_reset,
        reset_size=reset_size,
        reset_ratio=reset_ratio,
        max_context_size=max_context_size,
        memory_warning_threshold=memory_warning_threshold,
        keep_thinking=keep_thinking,
        reasoning_effort=reasoning_effort,
        reasoning_max_tokens=reasoning_max_tokens,
    )

    # Build directory name
    dir_name = f"inf_{strategy.value}_{config_basename}_{model_safe}{param_suffix}"

    if add_timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_name += f"_{timestamp}"

    output_dir = PROJECT_ROOT / "outputs" / dir_name
    return output_dir


def build_claude_api_output_dir(
    config_file: str,
    model: str,
    enable_thinking: bool = False,
    use_clear_tool_uses: bool = False,
    use_clear_thinking: bool = False,
    enable_code_execution: bool = False,
    enable_programmatic_tool_calling: bool = False,
    max_context_size: Optional[int] = None,
) -> Path:
    """Build the output directory path for Claude API benchmark results.

    Args:
        config_file: Config filename (basename extracted).
        model: Claude model name.
        enable_thinking: Whether extended thinking is enabled.
        use_clear_tool_uses: Whether clear tool uses is enabled.
        use_clear_thinking: Whether clear thinking is enabled.
        enable_code_execution: Whether code execution is enabled.
        enable_programmatic_tool_calling: Whether programmatic tool calling is enabled.
        max_context_size: Maximum context size in tokens.

    Returns:
        Path to output directory.
    """
    config_basename = Path(config_file).stem
    model_safe = sanitize_model_name(model)

    suffix = ""
    if enable_thinking:
        suffix += "_ET"
    if use_clear_tool_uses:
        suffix += "_CTU"
    if use_clear_thinking:
        suffix += "_CTH"
    if enable_code_execution:
        suffix += "_CE"
    if enable_programmatic_tool_calling:
        suffix += "_PTC"
    if max_context_size is not None:
        suffix += f"_MC{max_context_size}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"inf_claude_api_{config_basename}_{model_safe}{suffix}_{timestamp}"

    return PROJECT_ROOT / "outputs" / dir_name


def build_claude_agent_output_dir(
    config_file: str,
    use_clear_tool_uses: bool = False,
    use_clear_tool_results: bool = False,
    disable_prompt_caching: bool = False,
    disable_compact: bool = False,
    autocompact_pct: int = 80,
) -> Path:
    """Build the output directory path for Claude Agent SDK benchmark results.

    Args:
        config_file: Config filename (basename extracted).
        use_clear_tool_uses: Whether clear tool uses is enabled.
        use_clear_tool_results: Whether clear tool results is enabled.
        disable_prompt_caching: Whether prompt caching is disabled.
        disable_compact: Whether compaction is disabled.
        autocompact_pct: Autocompact percentage threshold.

    Returns:
        Path to output directory.
    """
    config_basename = Path(config_file).stem

    suffix = ""
    if use_clear_tool_uses:
        suffix += "_CTU"
    if use_clear_tool_results:
        suffix += "_CTR"
    if disable_prompt_caching:
        suffix += "_NPC"
    if disable_compact:
        suffix += "_NC"
    if autocompact_pct != 80:
        suffix += f"_AC{autocompact_pct}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"inf_claude_agent_{config_basename}{suffix}_{timestamp}"

    return PROJECT_ROOT / "outputs" / dir_name


def build_task_dir(output_dir: Path) -> Path:
    """Build the task directory path inside output directory.

    Args:
        output_dir: Path to output directory.

    Returns:
        Path to task directory.
    """
    return output_dir / "tasks"
