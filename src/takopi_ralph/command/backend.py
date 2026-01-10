"""Ralph command backend for takopi.

Provides /ralph command with project/branch targeting:

Usage: /ralph [project] [@branch] <command> [args...]

Examples:
  /ralph start                    - Current directory
  /ralph myproject start          - Specific project
  /ralph @feature start           - Current project, feature worktree
  /ralph myproject @feature start - Project + worktree
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from takopi.api import CommandContext, CommandResult, ConfigError, RunContext

from .context import RalphContext
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

if TYPE_CHECKING:
    from takopi.api import TransportRuntime

HELP_TEXT = """**Ralph - Autonomous Coding Loop**

Usage: `/ralph [project] [@branch] <command>`

Commands:
  `init`              - Interactive project setup
  `prd`               - Show PRD status
  `prd init`          - Create PRD from description
  `prd clarify [focus]` - Analyze and improve PRD
  `start`             - Start a Ralph loop
  `status`            - Show current status
  `stop`              - Gracefully stop the loop
  `reset [--all]`     - Reset circuit breaker

Examples:
  `/ralph init`                   # Current directory
  `/ralph myproject start`        # Specific project
  `/ralph myproject @feature prd` # Project on feature branch
  `/ralph @hotfix status`         # Current project, hotfix worktree
"""

# Commands that should not be confused with project names
RALPH_COMMANDS = frozenset({"init", "prd", "start", "status", "stop", "reset", "help"})


def _parse_project_branch(
    args: tuple[str, ...],
    project_aliases: set[str],
) -> tuple[str | None, str | None, tuple[str, ...]]:
    """Parse project and @branch from command args.

    Args:
        args: Full command args including 'ralph'
        project_aliases: Known project names from takopi config

    Returns:
        (project, branch, remaining_args)

    Examples:
        ('ralph', 'start') -> (None, None, ('start',))
        ('ralph', 'myproj', 'start') -> ('myproj', None, ('start',))
        ('ralph', '@feat', 'start') -> (None, 'feat', ('start',))
        ('ralph', 'myproj', '@feat', 'start') -> ('myproj', 'feat', ('start',))
    """
    project: str | None = None
    branch: str | None = None
    remaining = list(args[1:])  # Skip 'ralph'

    consumed = 0
    for token in remaining:
        # @branch token
        if token.startswith("@") and len(token) > 1:
            branch = token[1:]
            consumed += 1
            continue

        # Check if it's a known project (not a command)
        lower = token.lower()
        if lower in project_aliases and lower not in RALPH_COMMANDS:
            project = lower
            consumed += 1
            continue

        # Hit a command or unknown token - stop parsing context
        break

    return project, branch, tuple(remaining[consumed:])


def _resolve_ralph_context(
    project: str | None,
    branch: str | None,
    remaining_args: tuple[str, ...],
    runtime: TransportRuntime,
) -> RalphContext:
    """Resolve project/branch to RalphContext.

    Args:
        project: Project alias or None
        branch: Branch name or None
        remaining_args: Args after project/branch parsing (e.g. ("prd", "clarify"))
        runtime: Takopi runtime for resolution

    Returns:
        RalphContext with resolved cwd and args

    Raises:
        ConfigError: If project/branch cannot be resolved
    """
    if project is None and branch is None:
        # No explicit context - use current directory
        return RalphContext(run_context=None, cwd=Path.cwd(), args=remaining_args)

    run_ctx = RunContext(project=project, branch=branch)
    resolved_path = runtime.resolve_run_cwd(run_ctx)

    if resolved_path is None:
        if project:
            raise ConfigError(f"Could not resolve project: {project}")
        raise ConfigError(f"Could not resolve branch: @{branch}")

    return RalphContext(run_context=run_ctx, cwd=resolved_path, args=remaining_args)


class RalphCommand:
    """Ralph command backend for takopi."""

    id = "ralph"
    description = "Autonomous Ralph coding loop"

    async def handle(self, ctx: CommandContext) -> CommandResult | None:
        """Route /ralph commands to appropriate handlers."""

        # Handle callback queries from clarify flow
        if ctx.text.startswith(CLARIFY_CALLBACK_PREFIX):
            parts = ctx.text.split(":")
            if len(parts) >= 5:
                session_id = parts[3]
                answer = parts[4]
                return await handle_clarify_callback(ctx, session_id, answer)

        # Handle init flow callbacks (reserved for future use)
        if ctx.text.startswith(INIT_CALLBACK_PREFIX):
            return None

        # Parse project/branch from args
        project_aliases = set(ctx.runtime.project_aliases())
        project, branch, remaining_args = _parse_project_branch(
            ctx.args, project_aliases
        )

        # Resolve to RalphContext
        try:
            ralph_ctx = _resolve_ralph_context(project, branch, remaining_args, ctx.runtime)
        except ConfigError as e:
            return CommandResult(text=f"Error: {e}")

        # Check for pending sessions (using resolved cwd)
        if has_pending_prd_init_session(ralph_ctx.cwd) and not ctx.text.startswith("/"):
            return await handle_prd_init_input(ctx, ctx.text, ralph_ctx)

        if has_pending_init_session(ralph_ctx.cwd) and not ctx.text.startswith("/"):
            return await handle_init_topic_input(ctx, ctx.text, ralph_ctx)

        # Get subcommand from remaining args
        subcommand = remaining_args[0].lower() if remaining_args else ""

        if not subcommand:
            return CommandResult(text=HELP_TEXT)

        # Route to handler with ralph_ctx
        handlers = {
            "init": handle_init,
            "prd": handle_prd,
            "start": handle_start,
            "status": handle_status,
            "stop": handle_stop,
            "reset": handle_reset,
            "help": lambda ctx, ralph_ctx: CommandResult(text=HELP_TEXT),
        }

        handler = handlers.get(subcommand)
        if handler is None:
            return CommandResult(
                text=f"Unknown command: `{subcommand}`\n\n{HELP_TEXT}"
            )

        return await handler(ctx, ralph_ctx)


# Export the backend instance
BACKEND = RalphCommand()
