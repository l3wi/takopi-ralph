"""Handler for /ralph prd commands."""

from __future__ import annotations

import json
from pathlib import Path

from takopi.api import CommandContext, CommandResult

from ...clarify import (
    ClarifyFlow,
    PRDAnalyzer,
    get_questions_for_focus,
    parse_description_to_prd,
)
from ...prd import PRDManager
from .clarify import send_question

# Session storage filename for prd init
PRD_INIT_SESSIONS_FILE = "prd_init_sessions.json"


async def handle_prd(ctx: CommandContext) -> CommandResult | None:
    """Handle /ralph prd commands.

    Subcommands:
    - /ralph prd           - Show PRD status
    - /ralph prd init      - Create PRD from description
    - /ralph prd clarify   - Analyze and improve PRD
    """
    # Args: ["ralph", "prd", ...]
    args = ctx.args[2:] if len(ctx.args) > 2 else []

    if not args:
        return await handle_prd_status(ctx)

    subcommand = args[0].lower()

    if subcommand == "init":
        return await handle_prd_init(ctx)
    elif subcommand == "clarify":
        return await handle_prd_clarify(ctx)
    else:
        return CommandResult(
            text=f"Unknown prd subcommand: `{subcommand}`\n\n"
            "Usage:\n"
            "  `/ralph prd` - Show PRD status\n"
            "  `/ralph prd init` - Create initial PRD from description\n"
            "  `/ralph prd clarify [focus]` - Analyze and improve PRD"
        )


async def handle_prd_status(ctx: CommandContext) -> CommandResult | None:
    """Handle /ralph prd - show PRD status."""
    cwd = Path.cwd()
    prd_manager = PRDManager(cwd / "prd.json")

    if not prd_manager.exists():
        return CommandResult(
            text="**No PRD found**\n\n"
            "Run `/ralph prd init` to create one from a description, or\n"
            "`/ralph init` for full project setup."
        )

    prd = prd_manager.load()

    # Build status display
    lines = [
        f"## {prd.project_name}",
        "",
    ]

    if prd.description:
        # Truncate long descriptions
        desc = prd.description[:200] + "..." if len(prd.description) > 200 else prd.description
        lines.append(f"*{desc}*")
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


async def handle_prd_init(ctx: CommandContext) -> CommandResult | None:
    """Handle /ralph prd init - create PRD from description.

    If no PRD exists, prompts user for a detailed description,
    then parses it into a structured PRD.
    """
    cwd = Path.cwd()
    prd_manager = PRDManager(cwd / "prd.json")

    # Check if PRD already exists
    if prd_manager.exists():
        return CommandResult(
            text="**PRD already exists**\n\n"
            "Use `/ralph prd clarify` to analyze and improve it, or\n"
            "`/ralph prd` to view current status."
        )

    # Ensure .ralph directory exists
    (cwd / ".ralph").mkdir(parents=True, exist_ok=True)

    # Create pending session
    _create_prd_init_session(cwd)

    await ctx.executor.send(
        "**Create Initial PRD**\n\n"
        "Describe your project in detail. Include:\n"
        "• What you're building\n"
        "• Key features (MVP scope)\n"
        "• Tech stack (if decided)\n"
        "• Target users\n\n"
        "The more detail you provide, the better the initial PRD.\n\n"
        "*Reply with your project description.*"
    )

    return None


async def handle_prd_init_input(ctx: CommandContext, description: str) -> CommandResult | None:
    """Process the user's project description and create PRD.

    Called when user provides description after /ralph prd init.
    """
    cwd = Path.cwd()
    prd_manager = PRDManager(cwd / "prd.json")

    # Clear the pending session
    _delete_prd_init_session(cwd)

    # Parse description into PRD
    prd = parse_description_to_prd(description)

    # Save PRD
    prd_manager.save(prd)

    # Build response
    stories_text = "\n".join(f"  {s.id}. {s.title}" for s in prd.stories[:5])
    if len(prd.stories) > 5:
        stories_text += f"\n  ... and {len(prd.stories) - 5} more"

    return CommandResult(
        text=f"**PRD created for {prd.project_name}**\n\n"
        f"Generated {len(prd.stories)} user stories:\n{stories_text}\n\n"
        f"PRD saved to `prd.json`\n\n"
        f"Use `/ralph prd clarify` to refine it, or\n"
        f"`/ralph start` to begin implementation!"
    )


async def handle_prd_clarify(ctx: CommandContext) -> CommandResult | None:
    """Handle /ralph prd clarify [focus] - analyze and improve PRD.

    Two modes:
    - No args: Full PRD analysis, identify all gaps
    - With focus: Ask questions about specific area
    """
    cwd = Path.cwd()
    prd_manager = PRDManager(cwd / "prd.json")

    # Check PRD exists
    if not prd_manager.exists():
        return CommandResult(
            text="**No PRD found**\n\n"
            "Use `/ralph prd init` to create one first."
        )

    prd = prd_manager.load()

    # Ensure .ralph directory exists
    (cwd / ".ralph").mkdir(parents=True, exist_ok=True)

    # Check for focus text: /ralph prd clarify <focus>
    # Args: ["ralph", "prd", "clarify", ...]
    focus_args = ctx.args[3:] if len(ctx.args) > 3 else []
    focus = " ".join(focus_args) if focus_args else None

    # Initialize flow manager
    flow = ClarifyFlow(cwd / ".ralph")

    if focus:
        # Focused mode: ask questions about specific area
        questions = get_questions_for_focus(focus)

        if not questions:
            return CommandResult(
                text=f"Couldn't determine relevant questions for: *{focus}*\n\n"
                "Try being more specific, or use `/ralph prd clarify` without focus."
            )

        # Create session with focus-specific questions (enhance mode)
        session = flow.create_session(topic=prd.project_name, questions=questions, mode="enhance")

        await ctx.executor.send(
            f"**Clarifying:** {focus}\n\n"
            f"I'll ask {len(questions)} questions to enhance the PRD."
        )

        await send_question(ctx, session)
        return None

    else:
        # Full analysis mode
        analyzer = PRDAnalyzer()
        gaps = analyzer.analyze(prd)

        if not gaps:
            return CommandResult(
                text=f"**PRD for {prd.project_name} looks complete!**\n\n"
                f"{prd.total_count()} stories defined with good coverage.\n\n"
                "Use `/ralph start` to begin implementation, or\n"
                "`/ralph prd clarify <focus>` to add specific features."
            )

        # Get questions for gaps
        questions = analyzer.get_questions_for_gaps(gaps)

        if not questions:
            return CommandResult(
                text="**PRD analysis complete**\n\n"
                "Found some gaps but no additional questions needed.\n"
                "Use `/ralph prd clarify <focus>` to add specific features."
            )

        # Create session with gap-specific questions (enhance mode)
        session = flow.create_session(topic=prd.project_name, questions=questions, mode="enhance")

        # Format gaps for display
        gap_list = "\n".join(
            f"• {gap.value.replace('_', ' ').title()}" for gap in gaps
        )

        await ctx.executor.send(
            f"**Analyzing {prd.project_name} PRD...**\n\n"
            f"Found areas to improve:\n{gap_list}\n\n"
            f"I'll ask {len(questions)} questions to enhance the PRD."
        )

        await send_question(ctx, session)
        return None


# --- PRD Init Session Management ---


def _get_sessions_file(cwd: Path) -> Path:
    """Get path to prd init sessions file."""
    return cwd / ".ralph" / PRD_INIT_SESSIONS_FILE


def _create_prd_init_session(cwd: Path) -> None:
    """Create a pending prd init session."""
    sessions_file = _get_sessions_file(cwd)
    sessions_file.parent.mkdir(parents=True, exist_ok=True)
    sessions_file.write_text(json.dumps({"pending": True}))


def _delete_prd_init_session(cwd: Path) -> None:
    """Delete the pending prd init session."""
    sessions_file = _get_sessions_file(cwd)
    if sessions_file.exists():
        sessions_file.unlink()


def has_pending_prd_init_session(cwd: Path) -> bool:
    """Check if there's a pending prd init session waiting for input."""
    sessions_file = _get_sessions_file(cwd)
    if not sessions_file.exists():
        return False

    try:
        data = json.loads(sessions_file.read_text())
        return data.get("pending", False)
    except (json.JSONDecodeError, OSError):
        return False
