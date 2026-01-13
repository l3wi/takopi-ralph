"""Handler for /ralph start command."""

from __future__ import annotations

from takopi.api import CommandContext, CommandResult, RunRequest

from ...circuit_breaker import CircuitBreaker
from ...prd import PRDManager
from ...state import LoopStatus, StateManager
from ..context import RalphContext

# Maximum iterations per start command to prevent runaway loops
MAX_ITERATIONS_PER_START = 50


async def handle_start(
    ctx: CommandContext,
    ralph_ctx: RalphContext,
) -> CommandResult | None:
    """Handle /ralph [project] [@branch] start command.

    Starts or continues a Ralph loop for the resolved project context.
    Runs iterations until exit condition is met or max iterations reached.
    """
    cwd = ralph_ctx.cwd

    # Initialize managers
    prd_manager = PRDManager(cwd / "prd.json")
    state_manager = StateManager(cwd / ".ralph")
    circuit_breaker = CircuitBreaker(cwd / ".ralph")

    # Check current state
    current_state = state_manager.load() if state_manager.exists() else None
    is_resuming = current_state and current_state.status == LoopStatus.PAUSED

    # Check if already running (but allow resuming from PAUSED)
    if state_manager.is_running():
        return CommandResult(
            text=f"A Ralph loop is already running for <b>{ralph_ctx.context_label()}</b>.\n"
            "Use /ralph stop first.",
            extra={"parse_mode": "HTML"},
        )

    # Check circuit breaker
    if not circuit_breaker.can_execute():
        status = circuit_breaker.get_status()
        return CommandResult(
            text=f"Circuit breaker is OPEN: {status.get('reason')}\n"
            "Use /ralph reset to reset it.",
        )

    # Check for PRD
    if not prd_manager.exists():
        return CommandResult(
            text=f"No prd.json found in <b>{ralph_ctx.context_label()}</b>.\n"
            "Use /ralph init or /ralph prd init to create one first.",
            extra={"parse_mode": "HTML"},
        )

    prd = prd_manager.load()
    if prd.all_complete():
        return CommandResult(
            text=f"All {prd.total_count()} stories are already complete!",
        )

    # Start or resume the session
    if is_resuming:
        # Resume from paused - just set back to RUNNING
        current_state.status = LoopStatus.RUNNING
        current_state.exit_reason = ""
        state_manager.save(current_state)
    else:
        # Fresh start
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
    if is_resuming:
        await ctx.executor.send(
            f"Resuming Ralph loop for <b>{ralph_ctx.context_label()}</b>\n"
            f"Progress: {prd.progress_summary()}\n"
            f"Continuing from loop {current_state.current_loop}\n"
            f"Current task: {story_info}",
            extra={"parse_mode": "HTML"},
        )
    else:
        await ctx.executor.send(
            f"Starting Ralph loop for <b>{ralph_ctx.context_label()}</b>\n"
            f"Progress: {prd.progress_summary()}\n"
            f"First task: {story_info}",
            extra={"parse_mode": "HTML"},
        )

    # Run the loop
    iteration = 0
    while iteration < MAX_ITERATIONS_PER_START:
        iteration += 1

        # Check circuit breaker before each iteration
        if not circuit_breaker.can_execute():
            status = circuit_breaker.get_status()
            state_manager.end_session(
                f"Circuit breaker opened: {status.get('reason')}", LoopStatus.HALTED
            )
            # Get last result for context
            state = state_manager.load()
            last_result_info = ""
            if state.recent_results:
                last = state.recent_results[-1]
                last_result_info = (
                    f"\n<b>Last loop:</b>\n"
                    f"  Errors: {last.error_count}\n"
                    f"  Tests: {last.tests_status.value}\n"
                    f"  Recommendation: {last.recommendation or 'N/A'}"
                )
            return CommandResult(
                text=f"🛑 <b>Ralph loop halted</b> after {iteration} iterations.\n\n"
                f"<b>Reason:</b> {status.get('reason')}\n"
                f"<b>No progress loops:</b> {status.get('consecutive_no_progress', 0)}\n"
                f"<b>Error loops:</b> {status.get('consecutive_same_error', 0)}"
                f"{last_result_info}\n\n"
                "Use <code>/ralph reset</code> to reset circuit breaker and try again.",
                extra={"parse_mode": "HTML"},
            )

        # Check if state says we should stop (e.g., from /ralph stop)
        state = state_manager.load()
        if state.status != LoopStatus.RUNNING:
            return CommandResult(
                text=f"Ralph loop completed after {iteration} iterations.\n"
                f"Reason: {state.exit_reason or 'Unknown'}",
            )

        # Get current story info for this iteration
        prd = prd_manager.load()
        next_story = prd.next_story()
        if next_story:
            current_task = f"Story #{next_story.id}: {next_story.title}"
        else:
            current_task = "Finishing up"

        # Send loop start message to chat so user can see progress
        await ctx.executor.send(
            f"<b>Loop {iteration}</b> — {current_task}",
            extra={"parse_mode": "HTML"},
        )

        # Build prompt
        if iteration == 1:
            prompt = f"Start working on the project. Focus on: {current_task}"
        else:
            prompt = f"Continue working. Current task: {current_task}"

        # Run one iteration (mode="emit" streams output to chat)
        await ctx.executor.run_one(
            RunRequest(
                prompt=prompt,
                engine="ralph_engine",
            ),
            mode="emit",
        )

        # Reload state after iteration to check exit conditions and show summary
        state = state_manager.load()

        # Show loop result summary
        if state.recent_results:
            last_result = state.recent_results[-1]
            work_type_label = last_result.work_type.value.lower().capitalize()

            if last_result.error_count > 0 or last_result.is_stuck:
                await ctx.executor.send(
                    f"⚠️ <b>Loop {iteration} ({work_type_label}) had issues:</b>\n"
                    f"  Errors detected: {last_result.error_count}\n"
                    f"  Files modified: {last_result.files_modified}\n"
                    f"  Tests: {last_result.tests_status.value}\n"
                    f"  Recommendation: {last_result.recommendation or 'Continue working'}",
                    extra={"parse_mode": "HTML"},
                )
            elif last_result.current_story_complete:
                # Story was explicitly marked complete by Claude
                prd_check = prd_manager.load()
                progress = prd_check.progress_summary()
                await ctx.executor.send(
                    f"✅ <b>Story completed!</b> ({work_type_label}) — Progress: {progress}",
                    extra={"parse_mode": "HTML"},
                )
            elif last_result.has_completion_signal:
                # General completion signal (e.g., all done)
                prd_check = prd_manager.load()
                progress = prd_check.progress_summary()
                await ctx.executor.send(
                    f"✅ <b>Loop {iteration} done</b> ({work_type_label}) — Progress: {progress}",
                    extra={"parse_mode": "HTML"},
                )
            elif last_result.files_modified > 0:
                # Show brief progress for successful iterations with changes
                files = last_result.files_modified
                await ctx.executor.send(
                    f"📝 <b>Loop {iteration}</b> ({work_type_label}) — {files} files modified",
                    extra={"parse_mode": "HTML"},
                )
        if state.status != LoopStatus.RUNNING:
            return CommandResult(
                text=f"Ralph loop completed after {iteration} iterations.\n"
                f"Reason: {state.exit_reason or 'Task complete'}",
            )

        # Check PRD completion
        prd = prd_manager.load()
        if prd.all_complete():
            state_manager.end_session("All stories complete", LoopStatus.COMPLETED)
            return CommandResult(
                text=f"Ralph loop completed after {iteration} iterations.\n"
                f"All {prd.total_count()} stories are complete!",
            )

    # Hit iteration limit for this start command - mark as PAUSED so we can resume
    state = state_manager.load()
    state.status = LoopStatus.PAUSED
    state.exit_reason = f"Paused after {MAX_ITERATIONS_PER_START} iterations (safety limit)"
    state_manager.save(state)

    return CommandResult(
        text=f"Ralph loop paused after {MAX_ITERATIONS_PER_START} iterations.\n"
        "Run /ralph start again to continue, or /ralph status to check progress.",
    )
