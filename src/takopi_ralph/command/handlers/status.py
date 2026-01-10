"""Handler for /ralph status command."""

from __future__ import annotations

from takopi.api import CommandContext, CommandResult

from ..context import RalphContext
from ...circuit_breaker import CircuitBreaker
from ...prd import PRDManager
from ...state import StateManager


async def handle_status(
    ctx: CommandContext,
    ralph_ctx: RalphContext,
) -> CommandResult | None:
    """Handle /ralph [project] [@branch] status command.

    Shows current Ralph loop status for the resolved context.
    """
    cwd = ralph_ctx.cwd

    # Initialize managers
    prd_manager = PRDManager(cwd / "prd.json")
    state_manager = StateManager(cwd / ".ralph")
    circuit_breaker = CircuitBreaker(cwd / ".ralph")

    lines = [f"## Ralph Status: {ralph_ctx.context_label()}"]

    # State info
    if state_manager.exists():
        state = state_manager.load()
        lines.append(f"**Status:** {state.status.value}")
        lines.append(f"**Loop:** {state.current_loop}/{state.max_loops}")

        if state.exit_reason:
            lines.append(f"**Exit reason:** {state.exit_reason}")

        if state.recent_results:
            last = state.recent_results[-1]
            lines.append(f"**Last work:** {last.work_type.value}")
            lines.append(f"**Files modified:** {last.files_modified}")
            lines.append(f"**Confidence:** {last.confidence_score}%")
    else:
        lines.append("*No active session*")

    lines.append("")

    # Circuit breaker
    lines.append("## Circuit Breaker")
    cb_status = circuit_breaker.get_status()
    cb_state = cb_status.get("state", "CLOSED")

    state_emoji = {"CLOSED": "green", "HALF_OPEN": "yellow", "OPEN": "red"}.get(cb_state, "")
    lines.append(f"**State:** {cb_state} ({state_emoji})")

    if cb_status.get("reason"):
        lines.append(f"**Reason:** {cb_status['reason']}")

    lines.append(f"**No progress loops:** {cb_status.get('consecutive_no_progress', 0)}")
    lines.append(f"**Error loops:** {cb_status.get('consecutive_same_error', 0)}")

    lines.append("")

    # PRD progress
    lines.append("## Stories")
    if prd_manager.exists():
        prd = prd_manager.load()
        lines.append(f"**Project:** {prd.project_name}")
        lines.append(f"**Progress:** {prd.progress_summary()}")

        # List pending stories
        pending = [s for s in prd.stories if not s.passes]
        if pending:
            lines.append("")
            lines.append("**Pending:**")
            for story in pending[:5]:  # Show first 5
                lines.append(f"  {story.id}. {story.title}")
            if len(pending) > 5:
                lines.append(f"  ... and {len(pending) - 5} more")
    else:
        lines.append("*No prd.json found*")

    return CommandResult(text="\n".join(lines))
