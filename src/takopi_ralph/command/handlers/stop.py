"""Handler for /ralph stop command."""

from __future__ import annotations

from takopi.api import CommandContext, CommandResult

from ...prd import PRDManager
from ...state import LoopStatus, StateManager
from ..context import RalphContext


async def handle_stop(
    ctx: CommandContext,
    ralph_ctx: RalphContext,
) -> CommandResult | None:
    """Handle /ralph [project] [@branch] stop command.

    Gracefully stops the Ralph loop for the resolved context.
    """
    cwd = ralph_ctx.cwd

    # Initialize managers
    prd_manager = PRDManager(cwd / "prd.json")
    state_manager = StateManager(cwd / ".ralph")

    if not state_manager.exists():
        return CommandResult(
            text=f"No Ralph session to stop in <b>{ralph_ctx.context_label()}</b>.",
            extra={"parse_mode": "HTML"},
        )

    state = state_manager.load()

    if state.status != LoopStatus.RUNNING:
        return CommandResult(text=f"Ralph is not running. Current status: {state.status.value}")

    # End session
    state_manager.end_session("User requested stop", LoopStatus.COMPLETED)

    # Generate summary
    lines = [f"<b>Ralph Stopped: {ralph_ctx.context_label()}</b>"]
    lines.append(f"<b>Loops completed:</b> {state.current_loop}")

    if prd_manager.exists():
        prd = prd_manager.load()
        lines.append(f"<b>Stories:</b> {prd.progress_summary()}")

    if state.recent_results:
        lines.append("")
        lines.append("<b>Recent work:</b>")
        for result in state.recent_results[-3:]:
            lines.append(f"  Loop {result.loop_number}: {result.work_type.value}")

    return CommandResult(text="\n".join(lines), extra={"parse_mode": "HTML"})
