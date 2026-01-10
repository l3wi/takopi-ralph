"""Prompt augmentation for Ralph loops.

Adds Ralph instructions to Claude prompts including
the RALPH_STATUS block requirement.

Templates are loaded from clarify/templates/ directory.
"""

from __future__ import annotations

from ..clarify.prompt_loader import load_prompt
from ..prd import DEFAULT_FEEDBACK_COMMANDS, PRD, UserStory


def _format_feedback_commands(commands: dict[str, str]) -> str:
    """Format feedback commands for prompt injection."""
    lines = []
    for i, (name, cmd) in enumerate(commands.items(), 1):
        lines.append(f"{i}. **{name.title()}**: `{cmd}` must pass")
    return "\n".join(lines)


def _build_status_instructions(prd: PRD | None) -> str:
    """Build status instructions with feedback commands injected."""
    # Get feedback commands from PRD or use defaults
    if prd and prd.feedback_commands:
        feedback_section = _format_feedback_commands(prd.feedback_commands)
    else:
        feedback_section = _format_feedback_commands(DEFAULT_FEEDBACK_COMMANDS)

    return load_prompt("ralph_status", feedback_commands_section=feedback_section)


def _get_quality_instructions(quality_level: str) -> str:
    """Load quality level instructions from template.

    Args:
        quality_level: One of "prototype", "production", "library"

    Returns:
        Quality instructions text, or empty string if not found.
    """
    try:
        return load_prompt(f"quality_{quality_level}")
    except FileNotFoundError:
        return ""


def build_ralph_prompt(
    user_prompt: str,
    prd: PRD | None = None,
    current_story: UserStory | None = None,
    loop_number: int = 0,
    circuit_state: str = "CLOSED",
) -> str:
    """Build an augmented prompt with Ralph instructions.

    Args:
        user_prompt: Original user prompt
        prd: Current PRD (if loaded)
        current_story: Current story to work on
        loop_number: Current loop iteration
        circuit_state: Current circuit breaker state

    Returns:
        Augmented prompt with Ralph instructions
    """
    parts = []

    # Context header
    parts.append(f"# Ralph Loop #{loop_number}")
    parts.append(f"Circuit Breaker: {circuit_state}")
    parts.append("")

    # PRD context
    if prd:
        parts.append("## Project Context")
        parts.append(f"Project: {prd.project_name}")
        parts.append(f"Progress: {prd.progress_summary()}")
        parts.append("")

    # Quality-level instructions
    if prd:
        quality_instructions = _get_quality_instructions(prd.quality_level)
        if quality_instructions:
            parts.append(quality_instructions)

    # Current story
    if current_story:
        parts.append("## Current Task")
        parts.append(f"Story #{current_story.id}: {current_story.title}")
        parts.append(f"Description: {current_story.description}")
        if current_story.acceptance_criteria:
            parts.append("Acceptance Criteria:")
            for criterion in current_story.acceptance_criteria:
                parts.append(f"  - {criterion}")
        parts.append("")

    # User prompt
    parts.append("## Your Task")
    parts.append(user_prompt)
    parts.append("")

    # Ralph instructions with dynamic feedback commands
    parts.append(_build_status_instructions(prd))

    return "\n".join(parts)


def build_continuation_prompt(
    loop_number: int,
    prd: PRD | None = None,
    current_story: UserStory | None = None,
    circuit_state: str = "CLOSED",
) -> str:
    """Build a continuation prompt for the next loop iteration.

    Args:
        loop_number: Current loop iteration
        prd: Current PRD
        current_story: Current story to work on
        circuit_state: Current circuit breaker state

    Returns:
        Continuation prompt
    """
    parts = []

    parts.append(f"# Ralph Loop #{loop_number} - Continuation")
    parts.append(f"Circuit Breaker: {circuit_state}")
    parts.append("")

    if prd:
        parts.append(f"Progress: {prd.progress_summary()}")
        parts.append("")

        # Quality-level instructions
        quality_instructions = _get_quality_instructions(prd.quality_level)
        if quality_instructions:
            parts.append(quality_instructions)

    if current_story:
        parts.append(f"Continue working on Story #{current_story.id}: {current_story.title}")
        parts.append("")
        parts.append("Focus on ONE task at a time. When complete, update the story status.")
    else:
        parts.append(
            "All stories appear complete. Verify everything works "
            "and set EXIT_SIGNAL: true if done."
        )

    parts.append("")
    parts.append(_build_status_instructions(prd))

    return "\n".join(parts)
