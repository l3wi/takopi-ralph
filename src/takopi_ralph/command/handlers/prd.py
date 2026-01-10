"""Handler for /ralph prd commands."""

from __future__ import annotations

from pathlib import Path

from takopi.api import CommandContext, CommandResult

from ...clarify import ClarifyFlow
from ...clarify.questions import get_all_questions
from ...prd import PRDManager
from .clarify import send_question


async def handle_prd(ctx: CommandContext) -> CommandResult | None:
    """Handle /ralph prd commands.

    Subcommands:
    - /ralph prd          - Show PRD status
    - /ralph prd clarify  - Start clarify flow
    """
    # Args: ["ralph", "prd", ...]
    args = ctx.args[2:] if len(ctx.args) > 2 else []

    if not args:
        return await handle_prd_status(ctx)

    subcommand = args[0].lower()

    if subcommand == "clarify":
        return await handle_prd_clarify(ctx)
    else:
        return CommandResult(
            text=f"Unknown prd subcommand: `{subcommand}`\n\n"
            "Usage:\n"
            "  `/ralph prd` - Show PRD status\n"
            "  `/ralph prd clarify <topic>` - Start requirements gathering"
        )


async def handle_prd_status(ctx: CommandContext) -> CommandResult | None:
    """Handle /ralph prd - show PRD status."""
    cwd = Path.cwd()
    prd_manager = PRDManager(cwd / "prd.json")

    if not prd_manager.exists():
        return CommandResult(
            text="**No PRD found**\n\n"
            "Run `/ralph init` to set up a new project, or\n"
            "`/ralph prd clarify <topic>` to start requirements gathering."
        )

    prd = prd_manager.load()

    # Build status display
    lines = [
        f"## {prd.project_name}",
        "",
    ]

    if prd.description:
        lines.append(f"*{prd.description}*")
        lines.append("")

    lines.append(f"**Progress:** {prd.completed_count()}/{prd.total_count()} stories complete")
    lines.append("")

    # Story list with status indicators
    if prd.stories:
        lines.append("**Stories:**")
        for story in prd.stories:
            status_icon = "[x]" if story.passes else "[ ]"
            lines.append(f"  {status_icon} {story.id}. {story.title}")

    # Next story hint
    next_story = prd.next_story()
    if next_story:
        lines.append("")
        lines.append(f"**Next:** {next_story.title}")

    return CommandResult(text="\n".join(lines))


async def handle_prd_clarify(ctx: CommandContext) -> CommandResult | None:
    """Handle /ralph prd clarify <topic> command.

    Starts interactive requirements gathering flow.
    """
    cwd = Path.cwd()

    # Args: ["ralph", "prd", "clarify", ...]
    args = ctx.args[3:] if len(ctx.args) > 3 else []

    if not args:
        return CommandResult(
            text="Usage: `/ralph prd clarify <topic>`\n"
            "Example: `/ralph prd clarify Task management app`"
        )

    topic = " ".join(args)

    # Ensure .ralph directory exists
    (cwd / ".ralph").mkdir(parents=True, exist_ok=True)

    # Initialize flow manager
    flow = ClarifyFlow(cwd / ".ralph")

    # Create new session
    session = flow.create_session(topic)

    # Send intro message
    questions = get_all_questions()
    await ctx.executor.send(
        f"Starting requirements gathering for **{topic}**\n\n"
        f"I'll ask you {len(questions)} questions to understand your needs.\n"
        f"Tap the buttons to answer, or skip questions you're unsure about."
    )

    # Send first question
    await send_question(ctx, session)

    return None  # Don't send automatic response
