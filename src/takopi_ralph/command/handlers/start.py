"""Handler for /ralph start command."""

from __future__ import annotations

from takopi.api import CommandContext, CommandResult, RunRequest

from ...circuit_breaker import CircuitBreaker
from ...prd import PRDManager
from ...state import StateManager
from ..context import RalphContext


async def handle_start(
    ctx: CommandContext,
    ralph_ctx: RalphContext,
) -> CommandResult | None:
    """Handle /ralph [project] [@branch] start command.

    Starts a Ralph loop for the resolved project context.
    """
    cwd = ralph_ctx.cwd

    # Initialize managers
    prd_manager = PRDManager(cwd / "prd.json")
    state_manager = StateManager(cwd / ".ralph")
    circuit_breaker = CircuitBreaker(cwd / ".ralph")

    # Check if already running
    if state_manager.is_running():
        return CommandResult(
            text=f"A Ralph loop is already running for **{ralph_ctx.context_label()}**.\n"
            "Use /ralph stop first.",
        )

    # Check circuit breaker
    if not circuit_breaker.can_execute():
        status = circuit_breaker.get_status()
        return CommandResult(
            text=f"Circuit breaker is OPEN: {status.get('reason')}\n"
            f"Use /ralph reset to reset it.",
        )

    # Check for PRD
    if not prd_manager.exists():
        return CommandResult(
            text=f"No prd.json found in **{ralph_ctx.context_label()}**.\n"
            "Use /ralph init or /ralph prd init to create one first.",
        )

    prd = prd_manager.load()
    if prd.all_complete():
        return CommandResult(
            text=f"All {prd.total_count()} stories are already complete!",
        )

    # Start the session
    state_manager.start_session(
        project_name=prd.project_name or ralph_ctx.context_label(),
        max_loops=100,
    )

    # Get next story
    next_story = prd.next_story()
    story_info = (
        f"Story #{next_story.id}: {next_story.title}" if next_story else "No pending stories"
    )

    # Send status message
    await ctx.executor.send(
        f"Starting Ralph loop for **{ralph_ctx.context_label()}**\n"
        f"Progress: {prd.progress_summary()}\n"
        f"First task: {story_info}"
    )

    # Run the first iteration using the ralph engine
    await ctx.executor.run_one(
        RunRequest(
            prompt=f"Start working on the project. Focus on: {story_info}",
            engine="ralph",
        ),
        mode="emit",  # Send output to chat
    )

    return CommandResult(
        text="Ralph loop started. Use /ralph status to check progress.",
    )
