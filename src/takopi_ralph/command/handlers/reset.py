"""Handler for /ralph reset command."""

from __future__ import annotations

from pathlib import Path

from takopi.api import CommandContext, CommandResult

from ...circuit_breaker import CircuitBreaker
from ...state import StateManager


async def handle_reset(ctx: CommandContext) -> CommandResult | None:
    """Handle /ralph reset command.

    Resets the circuit breaker and optionally the session state.
    """
    cwd = Path.cwd()
    args = ctx.args[1:] if len(ctx.args) > 1 else []

    # Initialize managers
    state_manager = StateManager(cwd / ".ralph")
    circuit_breaker = CircuitBreaker(cwd / ".ralph")

    # Check for --all flag
    reset_all = "--all" in args or "-a" in args

    lines = []

    # Reset circuit breaker
    circuit_breaker.reset("User requested reset")
    lines.append("Circuit breaker reset to CLOSED")

    # Optionally reset state
    if reset_all:
        state_manager.reset()
        lines.append("Session state cleared")

    return CommandResult(text="\n".join(lines))
