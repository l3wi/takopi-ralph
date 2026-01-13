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

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from takopi.api import CommandContext, CommandResult, ConfigError, RunContext

from .context import RalphContext
from .handlers.clarify import (
    CLARIFY_CALLBACK_PREFIX,
    handle_clarify_callback,
    handle_clarify_response,
    has_active_clarify_session,
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

HELP_TEXT = """<b>Ralph — Autonomous Coding Loop</b>

Usage: <code>/ralph [project] [@branch] &lt;command&gt;</code>

<b>Commands:</b>
  <code>init</code>              Interactive project setup
  <code>prd</code>               Show PRD status
  <code>prd init</code>          Create PRD from description
  <code>prd clarify</code>       Analyze and improve PRD
  <code>prd fix</code>           Auto-fix invalid PRD schema
  <code>prd show</code>          Show raw PRD JSON
  <code>start</code>             Start a Ralph loop
  <code>status</code>            Show current status
  <code>stop</code>              Gracefully stop the loop
  <code>reset [--all]</code>     Reset circuit breaker
  <code>help</code>              Show this help

<b>Examples:</b>
  <code>/ralph init</code>                   Current directory
  <code>/ralph myproject start</code>        Specific project
  <code>/ralph myproject @feature prd</code> Project on feature branch
  <code>/ralph @hotfix status</code>         Current project, hotfix worktree
"""

# Commands that should not be confused with project names
RALPH_COMMANDS = frozenset({"init", "prd", "start", "status", "stop", "reset", "help"})

# Topic state filename (must match takopi's STATE_FILENAME)
TOPIC_STATE_FILENAME = "telegram_topics_state.json"


def _read_topic_context(
    config_path: Path | None,
    chat_id: int | str | None,
    thread_id: int | str | None,
) -> RunContext | None:
    """Read topic context from takopi's topic state file.

    Args:
        config_path: Path to takopi config file
        chat_id: Telegram chat ID
        thread_id: Telegram thread ID (message_thread_id)

    Returns:
        RunContext if found, None otherwise
    """
    if config_path is None or chat_id is None or thread_id is None:
        return None

    state_path = config_path.with_name(TOPIC_STATE_FILENAME)
    if not state_path.exists():
        return None

    try:
        data = json.loads(state_path.read_text())
        threads = data.get("threads", {})
        thread_key = f"{chat_id}:{thread_id}"
        thread = threads.get(thread_key)
        if thread is None:
            return None

        raw_context = thread.get("context")
        if not isinstance(raw_context, dict):
            return None

        payload = cast(dict[str, Any], raw_context)
        project = payload.get("project")
        branch = payload.get("branch")

        if project is not None and isinstance(project, str):
            project = project.strip() or None
        else:
            project = None

        branch = branch.strip() or None if branch is not None and isinstance(branch, str) else None

        if project is None and branch is None:
            return None

        return RunContext(project=project, branch=branch)
    except (json.JSONDecodeError, OSError):
        return None


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

    # Skip 'ralph' if present (depends on how takopi passes args)
    remaining = list(args[1:]) if args and args[0].lower() == "ralph" else list(args)

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
    config_path: Path | None = None,
    chat_id: int | str | None = None,
    thread_id: int | str | None = None,
) -> RalphContext:
    """Resolve project/branch to RalphContext.

    Args:
        project: Project alias or None
        branch: Branch name or None
        remaining_args: Args after project/branch parsing (e.g. ("prd", "clarify"))
        runtime: Takopi runtime for resolution
        config_path: Path to takopi config file (for topic state lookup)
        chat_id: Telegram chat ID (for context lookup)
        thread_id: Telegram thread ID (for topic context lookup)

    Returns:
        RalphContext with resolved cwd and args

    Raises:
        ConfigError: If project/branch cannot be resolved
    """
    # If no explicit project/branch, try topic context first (most specific)
    if project is None and branch is None and thread_id is not None:
        topic_ctx = _read_topic_context(config_path, chat_id, thread_id)
        if topic_ctx is not None:
            project = topic_ctx.project
            branch = topic_ctx.branch

    # If still no context, try default_context_for_chat (for direct chats)
    if project is None and branch is None and chat_id is not None:
        # default_context_for_chat expects int, but chat_id may be str
        cid = int(chat_id) if isinstance(chat_id, str) else chat_id
        ambient_ctx = runtime.default_context_for_chat(cid)
        if ambient_ctx is not None:
            project = ambient_ctx.project
            branch = ambient_ctx.branch

    # Still no context - use current directory
    if project is None and branch is None:
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

        # Check if this is a callback query (starts with known prefix)
        is_clarify_callback = ctx.text.startswith(CLARIFY_CALLBACK_PREFIX)
        is_init_callback = ctx.text.startswith(INIT_CALLBACK_PREFIX)

        # Handle init flow callbacks (reserved for future use)
        if is_init_callback:
            return None

        # Parse project/branch from args
        project_aliases = set(ctx.runtime.project_aliases())
        project, branch, remaining_args = _parse_project_branch(ctx.args, project_aliases)

        # Get chat_id and thread_id for context lookup
        chat_id = ctx.message.channel_id if ctx.message else None
        thread_id = ctx.message.thread_id if ctx.message else None

        # Resolve to RalphContext
        try:
            ralph_ctx = _resolve_ralph_context(
                project,
                branch,
                remaining_args,
                ctx.runtime,
                config_path=ctx.config_path,
                chat_id=chat_id,
                thread_id=thread_id,
            )
        except ConfigError as e:
            return CommandResult(text=f"Error: {e}")

        # Handle clarify callbacks (now that we have ralph_ctx with correct cwd)
        if is_clarify_callback:
            parts = ctx.text.split(":")
            if len(parts) >= 5:
                session_id = parts[3]
                answer = parts[4]
                return await handle_clarify_callback(ctx, session_id, answer, ralph_ctx.cwd)
            return None

        # Check for pending sessions (using resolved cwd)
        # Note: These check for text replies that don't start with /
        if has_pending_prd_init_session(ralph_ctx.cwd) and not ctx.text.startswith("/"):
            return await handle_prd_init_input(ctx, ctx.text, ralph_ctx)

        if has_pending_init_session(ralph_ctx.cwd) and not ctx.text.startswith("/"):
            return await handle_init_topic_input(ctx, ctx.text, ralph_ctx)

        if has_active_clarify_session(ralph_ctx.cwd) and not ctx.text.startswith("/"):
            return await handle_clarify_response(ctx, ctx.text, ralph_ctx.cwd)

        # Get subcommand from remaining args
        subcommand = remaining_args[0].lower() if remaining_args else ""

        if not subcommand:
            return CommandResult(text=HELP_TEXT, extra={"parse_mode": "HTML"})

        # Route to handler with ralph_ctx
        handlers = {
            "init": handle_init,
            "prd": handle_prd,
            "start": handle_start,
            "status": handle_status,
            "stop": handle_stop,
            "reset": handle_reset,
            "help": lambda ctx, ralph_ctx: CommandResult(
                text=HELP_TEXT, extra={"parse_mode": "HTML"}
            ),
        }

        handler = handlers.get(subcommand)
        if handler is None:
            return CommandResult(
                text=f"Unknown command: <code>{subcommand}</code>\n\n{HELP_TEXT}",
                extra={"parse_mode": "HTML"},
            )

        return await handler(ctx, ralph_ctx)


# Export the backend instance
BACKEND = RalphCommand()
