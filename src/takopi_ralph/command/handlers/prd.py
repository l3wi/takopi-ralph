"""Handler for /ralph prd commands."""

from __future__ import annotations

import json
from pathlib import Path

from takopi.api import CommandContext, CommandResult

from ...clarify import ClarifyFlow
from ...clarify.llm_analyzer import LLMAnalyzer
from ...prd import PRD, PRDManager
from ..context import RalphContext
from .clarify import send_question

# Session storage filename for prd init
PRD_INIT_SESSIONS_FILE = "prd_init_sessions.json"


async def handle_prd(
    ctx: CommandContext,
    ralph_ctx: RalphContext,
) -> CommandResult | None:
    """Handle /ralph [project] [@branch] prd commands.

    Subcommands:
    - /ralph prd           - Show PRD status
    - /ralph prd init      - Create PRD from description
    - /ralph prd clarify   - Analyze and improve PRD
    """
    # Args from ralph_ctx already have project/branch stripped
    # e.g. ("prd",) or ("prd", "clarify")
    args = ralph_ctx.args[1:] if len(ralph_ctx.args) > 1 else []

    if not args:
        return await handle_prd_status(ctx, ralph_ctx)

    subcommand = args[0].lower()

    if subcommand == "init":
        return await handle_prd_init(ctx, ralph_ctx)
    elif subcommand == "clarify":
        return await handle_prd_clarify(ctx, ralph_ctx)
    else:
        return CommandResult(
            text=f"Unknown prd subcommand: `{subcommand}`\n\n"
            "Usage:\n"
            "  `/ralph prd` - Show PRD status\n"
            "  `/ralph prd init` - Create initial PRD from description\n"
            "  `/ralph prd clarify [focus]` - Analyze and improve PRD"
        )


async def handle_prd_status(
    ctx: CommandContext,
    ralph_ctx: RalphContext,
) -> CommandResult | None:
    """Handle /ralph [project] [@branch] prd - show PRD status."""
    cwd = ralph_ctx.cwd
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


async def handle_prd_init(
    ctx: CommandContext,
    ralph_ctx: RalphContext,
) -> CommandResult | None:
    """Handle /ralph [project] [@branch] prd init - create PRD from description.

    If no PRD exists, prompts user for a detailed description,
    then uses LLM to analyze and create a structured PRD.
    """
    cwd = ralph_ctx.cwd
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
        "- What you're building\n"
        "- Key features (MVP scope)\n"
        "- Tech stack (if decided)\n"
        "- Target users\n\n"
        "The more detail you provide, the better the initial PRD.\n\n"
        "*Reply with your project description.*"
    )

    return None


async def handle_prd_init_input(
    ctx: CommandContext,
    description: str,
    ralph_ctx: RalphContext,
) -> CommandResult | None:
    """Process the user's project description and create PRD.

    Uses LLM to analyze description and either ask clarifying questions
    or generate initial user stories.
    """
    cwd = ralph_ctx.cwd
    prd_manager = PRDManager(cwd / "prd.json")
    flow = ClarifyFlow(cwd / ".ralph")

    # Clear the pending session
    _delete_prd_init_session(cwd)

    # Create empty PRD with project name extracted from description
    project_name = _extract_project_name(description)
    empty_prd = PRD(project_name=project_name, description=description)

    await ctx.executor.send(f"**Analyzing your project:** {project_name}...")

    # Use LLM to analyze and get questions/stories
    analyzer = LLMAnalyzer(ctx.executor)
    result = await analyzer.analyze(
        prd_json=empty_prd.model_dump_json(),
        mode="create",
        topic=project_name,
        description=description,
    )

    # If LLM has questions, start clarify flow
    if result.questions:
        # Convert questions to session format
        pending_questions = [
            {
                "question": q.question,
                "options": q.options,
                "context": q.context,
            }
            for q in result.questions
        ]

        session = flow.create_session(
            topic=project_name,
            mode="create",
            pending_questions=pending_questions,
        )

        # Store description in session for later use
        session.answers["_description"] = description
        flow.update_session(session)

        await ctx.executor.send(
            f"**{result.analysis}**\n\n"
            f"I have {len(result.questions)} questions to help create your PRD."
        )

        await send_question(ctx, session)
        return None

    # No questions - generate PRD directly from stories
    if result.suggested_stories:
        for story in result.suggested_stories:
            empty_prd.add_story(
                title=story.title,
                description=story.description,
                acceptance_criteria=story.acceptance_criteria,
                priority=story.priority,
            )

        prd_manager.save(empty_prd)

        stories_text = "\n".join(f"  {s.id}. {s.title}" for s in empty_prd.stories[:5])
        if len(empty_prd.stories) > 5:
            stories_text += f"\n  ... and {len(empty_prd.stories) - 5} more"

        return CommandResult(
            text=f"**PRD created for {project_name}**\n\n"
            f"{result.analysis}\n\n"
            f"Generated {len(empty_prd.stories)} user stories:\n{stories_text}\n\n"
            f"PRD saved to `prd.json`\n\n"
            f"Use `/ralph prd clarify` to refine it, or\n"
            f"`/ralph start` to begin implementation!"
        )

    # Fallback - create minimal PRD
    empty_prd.add_story(
        title="Project Setup",
        description="Initialize the project structure",
        acceptance_criteria=["Project scaffolded", "Dependencies installed"],
        priority=1,
    )
    prd_manager.save(empty_prd)

    return CommandResult(
        text=f"**PRD created for {project_name}**\n\n"
        "Created minimal PRD. Use `/ralph prd clarify` to add more stories."
    )


async def handle_prd_clarify(
    ctx: CommandContext,
    ralph_ctx: RalphContext,
) -> CommandResult | None:
    """Handle /ralph [project] [@branch] prd clarify [focus] - analyze and improve PRD.

    Uses LLM to analyze the PRD and identify gaps or improvements.
    """
    cwd = ralph_ctx.cwd
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
    # ralph_ctx.args = ("prd", "clarify", ...) after project/branch stripped
    focus_args = ralph_ctx.args[2:] if len(ralph_ctx.args) > 2 else []
    focus = " ".join(focus_args) if focus_args else None

    # Initialize flow manager
    flow = ClarifyFlow(cwd / ".ralph")

    await ctx.executor.send(
        f"**Analyzing {prd.project_name} PRD...**"
        + (f"\n*Focus: {focus}*" if focus else "")
    )

    # Use LLM to analyze PRD
    analyzer = LLMAnalyzer(ctx.executor)
    result = await analyzer.analyze(
        prd_json=prd.model_dump_json(),
        mode="enhance",
        focus=focus,
    )

    # If LLM has questions, start clarify flow
    if result.questions:
        pending_questions = [
            {
                "question": q.question,
                "options": q.options,
                "context": q.context,
            }
            for q in result.questions
        ]

        session = flow.create_session(
            topic=prd.project_name,
            mode="enhance",
            focus=focus,
            pending_questions=pending_questions,
        )

        await ctx.executor.send(
            f"**{result.analysis}**\n\n"
            f"I have {len(result.questions)} questions to improve the PRD."
        )

        await send_question(ctx, session)
        return None

    # No questions - apply suggested stories directly
    if result.suggested_stories:
        added_count = 0
        for story in result.suggested_stories:
            # Check for duplicates
            existing_titles = [s.title.lower() for s in prd.stories]
            if story.title.lower() not in existing_titles:
                prd.add_story(
                    title=story.title,
                    description=story.description,
                    acceptance_criteria=story.acceptance_criteria,
                    priority=story.priority,
                )
                added_count += 1

        if added_count > 0:
            prd_manager.save(prd)
            return CommandResult(
                text=f"**PRD Enhanced**\n\n"
                f"{result.analysis}\n\n"
                f"Added {added_count} new stories.\n"
                f"Total: {prd.total_count()} stories\n\n"
                f"Use `/ralph prd` to view the updated PRD."
            )

    # PRD looks complete
    return CommandResult(
        text=f"**PRD for {prd.project_name} looks complete!**\n\n"
        f"{result.analysis}\n\n"
        f"{prd.total_count()} stories defined.\n\n"
        "Use `/ralph start` to begin implementation, or\n"
        "`/ralph prd clarify <focus>` to add specific features."
    )


def _extract_project_name(description: str) -> str:
    """Extract project name from description.

    Looks for patterns like 'building a X', 'create a X', etc.
    Falls back to first few words.
    """
    import re

    # Try common patterns
    patterns = [
        r"(?:building|create|develop|make|implement)\s+(?:a|an|the)?\s*([A-Za-z0-9\s]+?)(?:\.|,|that|which|with|for)",
        r"^(?:a|an|the)?\s*([A-Za-z0-9\s]+?)(?:\.|,|that|which|with|for|-)",
    ]

    for pattern in patterns:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if len(name) > 3 and len(name) < 50:
                return name.title()

    # Fallback: first 3-4 words, capitalized
    words = description.split()[:4]
    return " ".join(words).title()[:40]


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
