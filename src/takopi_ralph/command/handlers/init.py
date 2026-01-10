"""Handler for /ralph init command - interactive project setup."""

from __future__ import annotations

from pathlib import Path

from takopi.api import CommandContext, CommandResult

from ...clarify import ClarifyFlow
from ...clarify.questions import get_all_questions
from ...init import InitFlow, InitPhase
from ...prd import PRDManager
from ...state import StateManager
from .clarify import send_question

# Callback data prefix for init responses
INIT_CALLBACK_PREFIX = "ralph:init:"


async def handle_init(ctx: CommandContext) -> CommandResult | None:
    """Handle /ralph init command.

    Starts interactive project setup:
    1. Checks if project already initialized
    2. Asks for project topic
    3. Checks environment (git, .ralph)
    4. Transitions to clarify flow
    """
    cwd = Path.cwd()

    # Check if already initialized with PRD
    prd_manager = PRDManager(cwd / "prd.json")
    if prd_manager.exists():
        prd = prd_manager.load()
        return CommandResult(
            text=f"Project already initialized: **{prd.project_name}**\n"
            f"Progress: {prd.progress_summary()}\n\n"
            f"Use `/ralph prd` to view status or `/ralph start` to begin."
        )

    # Check if loop is running
    state_manager = StateManager(cwd / ".ralph")
    if state_manager.exists() and state_manager.is_running():
        return CommandResult(
            text="A Ralph loop is currently running.\n"
            "Use `/ralph stop` first, then run `/ralph init`."
        )

    # Initialize flow and create session (retrieved later via get_pending_session)
    init_flow = InitFlow(cwd / ".ralph")
    init_flow.create_session()

    # Send topic prompt
    await ctx.executor.send(
        "**Project Setup**\n\n"
        "What are you building? Enter a short description:\n"
        "(Example: 'Task management app' or 'CLI tool for data processing')"
    )

    return None  # Wait for topic input


async def handle_init_topic_input(
    ctx: CommandContext,
    topic: str,
) -> CommandResult | None:
    """Handle topic input during init flow.

    Called when user sends a message while an init session is pending.

    Args:
        ctx: Command context
        topic: The project topic/description entered by user

    Returns:
        CommandResult or None
    """
    cwd = Path.cwd()

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

    # Transition to clarify flow
    clarify_flow = ClarifyFlow(cwd / ".ralph")
    clarify_session = clarify_flow.create_session(session.topic)

    session.clarify_session_id = clarify_session.id
    session.phase = InitPhase.CLARIFYING
    init_flow.update_session(session)

    # Build intro message
    questions = get_all_questions()
    warning_text = ""
    if warnings:
        warning_text = "\n".join(f"- {w}" for w in warnings)
        warning_text = f"\n**Warnings:**\n{warning_text}\n"

    await ctx.executor.send(
        f"Initializing project: **{session.topic}**\n"
        f"{warning_text}\n"
        f"I'll ask you {len(questions)} questions to understand your requirements.\n"
        f"Tap the buttons to answer, or skip questions you're unsure about."
    )

    # Send first clarify question
    await send_question(ctx, clarify_session)

    return None


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
