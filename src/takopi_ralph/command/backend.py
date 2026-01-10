"""Ralph command backend for takopi.

Provides /ralph command with subcommands:
- /ralph init - Interactive project setup
- /ralph prd - Show PRD status
- /ralph prd clarify <topic> - Interactive requirements gathering
- /ralph start [project] - Start a Ralph loop
- /ralph status - Show current status
- /ralph stop - Stop the loop
- /ralph reset - Reset circuit breaker
"""

from __future__ import annotations

from pathlib import Path

from takopi.api import CommandContext, CommandResult

from .handlers.clarify import (
    CLARIFY_CALLBACK_PREFIX,
    handle_clarify_callback,
)
from .handlers.init import (
    INIT_CALLBACK_PREFIX,
    handle_init,
    handle_init_topic_input,
    has_pending_init_session,
)
from .handlers.prd import handle_prd, handle_prd_init_input, has_pending_prd_init_session
from .handlers.reset import handle_reset
from .handlers.start import handle_start
from .handlers.status import handle_status
from .handlers.stop import handle_stop

HELP_TEXT = """**Ralph - Autonomous Coding Loop**

Commands:
  `/ralph init` - Interactive project setup
  `/ralph prd` - Show PRD status
  `/ralph prd init` - Create PRD from description
  `/ralph prd clarify [focus]` - Analyze and improve PRD
  `/ralph start [project]` - Start a Ralph loop
  `/ralph status` - Show current status
  `/ralph stop` - Gracefully stop the loop
  `/ralph reset [--all]` - Reset circuit breaker

Examples:
  `/ralph init`
  `/ralph prd init`
  `/ralph prd clarify Add OAuth support`
  `/ralph start`
"""


class RalphCommand:
    """Ralph command backend for takopi."""

    id = "ralph"
    description = "Autonomous Ralph coding loop"

    async def handle(self, ctx: CommandContext) -> CommandResult | None:
        """Route /ralph commands to appropriate handlers."""
        args = ctx.args
        cwd = Path.cwd()

        # Handle callback queries from clarify flow (new prefix: ralph:prd:clarify:...)
        if ctx.text.startswith(CLARIFY_CALLBACK_PREFIX):
            # Parse callback data: ralph:prd:clarify:{session_id}:{answer}
            parts = ctx.text.split(":")
            if len(parts) >= 5:
                session_id = parts[3]
                answer = parts[4]
                return await handle_clarify_callback(ctx, session_id, answer)

        # Handle init flow callbacks (reserved for future use)
        if ctx.text.startswith(INIT_CALLBACK_PREFIX):
            # Currently unused, but ready for future init-specific callbacks
            return None

        # Check for pending prd init session waiting for description input
        # If user sends plain text (not a command), treat it as description input
        if has_pending_prd_init_session(cwd) and not ctx.text.startswith("/"):
            return await handle_prd_init_input(ctx, ctx.text)

        # Check for pending init session waiting for topic input
        # If user sends plain text (not a command), treat it as topic input
        if has_pending_init_session(cwd) and not ctx.text.startswith("/"):
            return await handle_init_topic_input(ctx, ctx.text)

        # No subcommand - show help
        if not args or len(args) == 1:
            return CommandResult(text=HELP_TEXT)

        # Route to subcommand handler
        subcommand = args[1].lower() if len(args) > 1 else ""

        handlers = {
            "init": handle_init,
            "prd": handle_prd,
            "start": handle_start,
            "status": handle_status,
            "stop": handle_stop,
            "reset": handle_reset,
            "help": lambda ctx: CommandResult(text=HELP_TEXT),
        }

        handler = handlers.get(subcommand)
        if handler is None:
            return CommandResult(
                text=f"Unknown subcommand: `{subcommand}`\n\n{HELP_TEXT}"
            )

        return await handler(ctx)


# Export the backend instance
BACKEND = RalphCommand()
