"""Handler for /ralph status command."""

from __future__ import annotations

from takopi.api import CommandContext, CommandResult

from ...circuit_breaker import CircuitBreaker
from ...prd import PRDManager
from ...state import StateManager
from ..context import RalphContext


def _format_timestamp(dt) -> str:
    """Format datetime for display."""
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _format_duration(started_at, updated_at) -> str:
    """Format session duration."""
    if started_at is None:
        return ""
    delta = updated_at - started_at
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


async def handle_status(
    ctx: CommandContext,
    ralph_ctx: RalphContext,
) -> CommandResult | None:
    """Handle /ralph [project] [@branch] status command.

    Shows current Ralph loop status for the resolved context.
    This command is intercepted and does NOT pass to AI.
    """
    cwd = ralph_ctx.cwd

    # Initialize managers
    prd_manager = PRDManager(cwd / "prd.json")
    state_manager = StateManager(cwd / ".ralph")
    circuit_breaker = CircuitBreaker(cwd / ".ralph")

    lines = [f"## Ralph Status: {ralph_ctx.context_label()}"]

    # PRD info first - most important context
    lines.append("")
    lines.append("### PRD")
    if prd_manager.exists():
        # Validate PRD first to catch issues
        is_valid, errors = prd_manager.validate()
        if not is_valid:
            lines.append("⚠️ **PRD has validation errors:**")
            for err in errors[:3]:
                lines.append(f"  - {err}")
            if len(errors) > 3:
                lines.append(f"  - ... and {len(errors) - 3} more")
            lines.append("")
            lines.append("Run `/ralph prd fix` to auto-fix schema issues.")
            # Still try to load what we can
            prd = prd_manager.load()
            if prd.project_name:
                lines.append("")
                lines.append(f"**Project:** {prd.project_name} (may be incomplete)")
        else:
            prd = prd_manager.load()
            lines.append(f"**Project:** {prd.project_name or '(unnamed)'}")
            lines.append(f"**Quality:** {prd.quality_level}")
            lines.append(f"**Progress:** {prd.progress_summary()}")

        # Current/next task
        next_story = prd.next_story()
        if next_story:
            lines.append("")
            lines.append(f"**Next task:** #{next_story.id} {next_story.title}")
            if next_story.description:
                # Truncate long descriptions
                desc = next_story.description[:100]
                if len(next_story.description) > 100:
                    desc += "..."
                lines.append(f"  {desc}")
        elif prd.all_complete():
            lines.append("")
            lines.append("**All stories complete!**")
    else:
        lines.append("*No prd.json found — run `/ralph prd init` to create*")

    # Loop state
    lines.append("")
    lines.append("### Loop State")
    if state_manager.exists():
        state = state_manager.load()
        lines.append(f"**Status:** {state.status.value.upper()}")
        lines.append(f"**Loop:** {state.current_loop}/{state.max_loops}")

        # Session info
        if state.session_id:
            lines.append(f"**Session:** `{state.session_id[:12]}...`")
        lines.append(f"**Started:** {_format_timestamp(state.started_at)}")
        if state.current_loop > 0:
            duration = _format_duration(state.started_at, state.updated_at)
            lines.append(f"**Duration:** {duration}")

        if state.exit_reason:
            lines.append(f"**Exit reason:** {state.exit_reason}")

        # Consecutive counters
        lines.append("")
        lines.append("**Counters:**")
        lines.append(f"  Test-only loops: {state.consecutive_test_only}")
        lines.append(f"  Done signals: {state.consecutive_done_signals}")
        lines.append(f"  No progress: {state.consecutive_no_progress}")

        # Recent loop history (last 3)
        if state.recent_results:
            lines.append("")
            lines.append("**Recent loops:**")
            for result in state.recent_results[-3:]:
                status_icon = {
                    "COMPLETE": "+",
                    "IN_PROGRESS": "~",
                    "BLOCKED": "!",
                }.get(result.status, "?")
                if result.recommendation:
                    summary = result.recommendation[:50]
                else:
                    summary = result.work_type.value
                if len(result.recommendation) > 50:
                    summary += "..."
                lines.append(f"  [{status_icon}] Loop {result.loop_number}: {summary}")
    else:
        lines.append("*No active session — run `/ralph start` to begin*")

    # Circuit breaker
    lines.append("")
    lines.append("### Circuit Breaker")
    cb_status = circuit_breaker.get_status()
    cb_state = cb_status.get("state", "CLOSED")

    state_indicator = {"CLOSED": "OK", "HALF_OPEN": "WARN", "OPEN": "HALTED"}.get(
        cb_state, ""
    )
    lines.append(f"**State:** {cb_state} ({state_indicator})")

    if cb_status.get("reason"):
        lines.append(f"**Reason:** {cb_status['reason']}")

    lines.append(f"**No progress loops:** {cb_status.get('consecutive_no_progress', 0)}")
    lines.append(f"**Error loops:** {cb_status.get('consecutive_same_error', 0)}")

    # Pending stories list
    if prd_manager.exists():
        prd = prd_manager.load()
        pending = [s for s in prd.stories if not s.passes]
        if pending and len(pending) > 1:
            lines.append("")
            lines.append("### Pending Stories")
            for story in pending[:5]:
                lines.append(f"  {story.id}. {story.title}")
            if len(pending) > 5:
                lines.append(f"  ... and {len(pending) - 5} more")

    return CommandResult(text="\n".join(lines))
