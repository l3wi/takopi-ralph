"""Handler for /ralph reset command."""

from __future__ import annotations

from takopi.api import CommandContext, CommandResult

from ..context import RalphContext
from ...circuit_breaker import CircuitBreaker
from ...state import StateManager


async def handle_reset(
    ctx: CommandContext,
    ralph_ctx: RalphContext,
) -> CommandResult | None:
    """Handle /ralph [project] [@branch] reset command.

    Resets the circuit breaker and optionally the session state.
    """
    cwd = ralph_ctx.cwd

    # Get remaining args (after project/branch parsing)
    # Note: args parsing already stripped project/branch in backend
    args = ctx.args

    # Initialize managers
    state_manager = StateManager(cwd / ".ralph")
    circuit_breaker = CircuitBreaker(cwd / ".ralph")

    # Check for --all flag
    reset_all = "--all" in args or "-a" in args

    lines = [f"## Reset: {ralph_ctx.context_label()}"]

    # Reset circuit breaker
    circuit_breaker.reset("User requested reset")
    lines.append("Circuit breaker reset to CLOSED")

    # Optionally reset state
    if reset_all:
        state_manager.reset()
        lines.append("Session state cleared")

    return CommandResult(text="\n".join(lines))
