"""Handler for /ralph start command."""

from __future__ import annotations

from pathlib import Path

from takopi.api import CommandContext, CommandResult, RunRequest

from ...circuit_breaker import CircuitBreaker
from ...prd import PRDManager
from ...state import StateManager


async def handle_start(ctx: CommandContext) -> CommandResult | None:
    """Handle /ralph start [project] command.

    Starts a Ralph loop for the current project or specified project.
    """
    # Get project path from context or args
    args = ctx.args[1:] if len(ctx.args) > 1 else []
    project = args[0] if args else None

    # Resolve project path
    if project:
        # Try to resolve from takopi projects
        try:
            resolved = ctx.runtime.resolve_run_cwd(project)
            cwd = resolved or Path.cwd()
        except Exception:
            cwd = Path.cwd()
    else:
        cwd = Path.cwd()

    # Initialize managers
    prd_manager = PRDManager(cwd / "prd.json")
    state_manager = StateManager(cwd / ".ralph")
    circuit_breaker = CircuitBreaker(cwd / ".ralph")

    # Check if already running
    if state_manager.is_running():
        return CommandResult(
            text="A Ralph loop is already running. Use /ralph stop first.",
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
            text="No prd.json found. Use /ralph clarify to create one first.",
        )

    prd = prd_manager.load()
    if prd.all_complete():
        return CommandResult(
            text=f"All {prd.total_count()} stories are already complete!",
        )

    # Start the session
    state_manager.start_session(
        project_name=prd.project_name or str(cwd.name),
        max_loops=100,
    )

    # Get next story
    next_story = prd.next_story()
    story_info = (
        f"Story #{next_story.id}: {next_story.title}" if next_story else "No pending stories"
    )

    # Send status message
    await ctx.executor.send(
        f"Starting Ralph loop for **{prd.project_name}**\n"
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
