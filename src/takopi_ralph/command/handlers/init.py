"""Handler for /ralph init command - interactive project setup."""

from __future__ import annotations

from pathlib import Path

from takopi.api import CommandContext, CommandResult

from ...clarify import ClarifyFlow
from ...clarify.llm_analyzer import LLMAnalyzer
from ...init import InitFlow, InitPhase
from ...prd import PRD, PRDManager
from ...state import StateManager
from ..context import RalphContext
from .clarify import send_question

# Callback data prefix for init responses
INIT_CALLBACK_PREFIX = "ralph:init:"


async def handle_init(
    ctx: CommandContext,
    ralph_ctx: RalphContext,
) -> CommandResult | None:
    """Handle /ralph [project] [@branch] init command.

    This is an alias for /ralph prd init with additional environment checks.
    Starts interactive project setup:
    1. Checks if project already initialized
    2. Asks for project topic
    3. Checks environment (git, .ralph)
    4. Uses LLM to generate clarifying questions
    5. Transitions to clarify flow
    """
    cwd = ralph_ctx.cwd

    # Check if already initialized with PRD
    prd_manager = PRDManager(cwd / "prd.json")
    if prd_manager.exists():
        # Validate PRD to give more helpful message
        is_valid, errors = prd_manager.validate()
        prd = prd_manager.load()
        label = ralph_ctx.context_label()

        if not is_valid:
            error_lines = "\n".join(f"  • {e}" for e in errors[:3])
            return CommandResult(
                text=f"Project <b>{label}</b> has a <code>prd.json</code> "
                f"but it has validation errors:\n{error_lines}\n\n"
                "Run <code>/ralph prd fix</code> to auto-fix, or "
                "<code>/ralph prd show</code> to view raw JSON.",
                extra={"parse_mode": "HTML"},
            )

        return CommandResult(
            text=f"Project already initialized in <b>{label}</b>: <b>{prd.project_name}</b>\n"
            f"Progress: {prd.progress_summary()}\n\n"
            "<b>Commands:</b>\n"
            "  <code>/ralph prd</code> — View PRD status\n"
            "  <code>/ralph start</code> — Start implementation loop\n"
            "  <code>/ralph prd clarify</code> — Add more stories",
            extra={"parse_mode": "HTML"},
        )

    # Check if loop is running
    state_manager = StateManager(cwd / ".ralph")
    if state_manager.exists() and state_manager.is_running():
        return CommandResult(
            text="A Ralph loop is currently running.\n"
            "Use <code>/ralph stop</code> first, then run <code>/ralph init</code>.",
            extra={"parse_mode": "HTML"},
        )

    # Initialize flow and create session (retrieved later via get_pending_session)
    init_flow = InitFlow(cwd / ".ralph")
    init_flow.create_session()

    # Send topic prompt
    await ctx.executor.send(
        "<b>Project Setup</b>\n\n"
        "What are you building? Enter a short description:\n"
        "(Example: 'Task management app' or 'CLI tool for data processing')",
        extra={"parse_mode": "HTML"},
    )

    return None  # Wait for topic input


async def handle_init_topic_input(
    ctx: CommandContext,
    topic: str,
    ralph_ctx: RalphContext,
) -> CommandResult | None:
    """Handle topic input during init flow.

    Called when user sends a message while an init session is pending.
    Uses LLM to generate clarifying questions based on the topic.

    Args:
        ctx: Command context
        topic: The project topic/description entered by user
        ralph_ctx: Resolved project context

    Returns:
        CommandResult or None
    """
    cwd = ralph_ctx.cwd

    # Initialize managers
    init_flow = InitFlow(cwd / ".ralph")

    # Get pending session
    session = init_flow.get_pending_session()
    if not session:
        return None  # No pending session, ignore

    # Store topic
    session.topic = topic.strip()
    session.phase = InitPhase.CHECKING

    # Run environment checks
    checks = init_flow.check_environment(cwd)
    session.git_checked = True
    session.git_available = checks["git_available"]
    session.ralph_dir_exists = checks["ralph_dir_exists"]

    init_flow.update_session(session)

    # Collect warnings
    warnings = []
    if not session.git_available:
        warnings.append("No git repository detected. Consider running `git init`.")

    # Create .ralph directory
    (cwd / ".ralph").mkdir(parents=True, exist_ok=True)

    # Build intro message
    warning_text = ""
    if warnings:
        warning_text = "\n".join(f"• {w}" for w in warnings)
        warning_text = f"\n<b>Warnings:</b>\n{warning_text}\n"

    await ctx.executor.send(
        f"Initializing project: <b>{session.topic}</b>\n"
        f"{warning_text}\n"
        "Analyzing your project to generate relevant questions...",
        extra={"parse_mode": "HTML"},
    )

    # Use LLM to generate questions for this project
    empty_prd = PRD(project_name=session.topic, description=topic)
    analyzer = LLMAnalyzer(ctx.executor, cwd=cwd)

    result = await analyzer.analyze(
        prd_json=empty_prd.model_dump_json(),
        mode="create",
        topic=session.topic,
        description=topic,
    )

    # Create clarify session with LLM-generated questions
    clarify_flow = ClarifyFlow(cwd / ".ralph")

    if result.questions:
        pending_questions = [
            {
                "question": q.question,
                "options": q.options,
                "context": q.context,
            }
            for q in result.questions
        ]

        clarify_session = clarify_flow.create_session(
            topic=session.topic,
            mode="create",
            pending_questions=pending_questions,
        )

        # Store description for later PRD creation
        clarify_session.answers["_description"] = topic
        clarify_flow.update_session(clarify_session)

        session.clarify_session_id = clarify_session.id
        session.phase = InitPhase.CLARIFYING
        init_flow.update_session(session)

        await ctx.executor.send(
            f"<b>{result.analysis}</b>\n\n"
            f"I have {len(result.questions)} questions to help create your PRD.",
            extra={"parse_mode": "HTML"},
        )

        # Send first clarify question
        await send_question(ctx, clarify_session)
        return None

    # No questions needed - create PRD directly
    prd_manager = PRDManager(cwd / "prd.json")

    if result.suggested_stories:
        for story in result.suggested_stories:
            empty_prd.add_story(
                title=story.title,
                description=story.description,
                acceptance_criteria=story.acceptance_criteria,
                priority=story.priority,
            )

    # Always ensure at least one story
    if not empty_prd.stories:
        empty_prd.add_story(
            title="Project Setup",
            description="Initialize project structure and dependencies",
            acceptance_criteria=["Project scaffolded", "Dependencies installed"],
            priority=1,
        )

    prd_manager.save(empty_prd)

    # Clean up init session
    init_flow.delete_session(session.id)

    stories_text = "\n".join(f"  {s.id}. {s.title}" for s in empty_prd.stories[:5])
    if len(empty_prd.stories) > 5:
        stories_text += f"\n  ... and {len(empty_prd.stories) - 5} more"

    return CommandResult(
        text=f"<b>Project initialized: {session.topic}</b>\n\n"
        f"{result.analysis}\n\n"
        f"Generated {len(empty_prd.stories)} user stories:\n{stories_text}\n\n"
        f"PRD saved to <code>prd.json</code>\n"
        f"Run <code>/ralph start</code> to begin implementation!",
        extra={"parse_mode": "HTML"},
    )


def has_pending_init_session(cwd: Path) -> bool:
    """Check if there's a pending init session waiting for input.

    Args:
        cwd: Current working directory

    Returns:
        True if there's a pending session
    """
    init_flow = InitFlow(cwd / ".ralph")
    session = init_flow.get_pending_session()
    return session is not None and session.phase == InitPhase.TOPIC_INPUT
