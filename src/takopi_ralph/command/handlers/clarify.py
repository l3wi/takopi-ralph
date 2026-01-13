"""Handler for clarify flow with inline keyboard + text fallback.

Users can either:
- Click an inline keyboard button to select an option
- Reply with text (number, 'skip', or custom answer)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from takopi.api import CommandContext, CommandResult
from takopi.transport import RenderedMessage

from ...clarify import ClarifyFlow, ClarifySession
from ...clarify.llm_analyzer import LLMAnalyzer
from ...prd import PRD, PRDManager

# Callback data prefix for clarify responses
CLARIFY_CALLBACK_PREFIX = "ralph:prd:clarify:"

# Session file for tracking active clarify sessions
CLARIFY_SESSION_FILE = "clarify_session.json"


def _get_session_file(cwd: Path) -> Path:
    """Get path to active clarify session file."""
    return cwd / ".ralph" / CLARIFY_SESSION_FILE


def has_active_clarify_session(cwd: Path) -> bool:
    """Check if there's an active clarify session waiting for input."""
    session_file = _get_session_file(cwd)
    if not session_file.exists():
        return False

    try:
        data = json.loads(session_file.read_text())
        return bool(data.get("session_id"))
    except (json.JSONDecodeError, OSError):
        return False


def _save_active_session(cwd: Path, session_id: str) -> None:
    """Save the active clarify session ID."""
    session_file = _get_session_file(cwd)
    session_file.parent.mkdir(parents=True, exist_ok=True)
    session_file.write_text(json.dumps({"session_id": session_id}))


def _get_active_session_id(cwd: Path) -> str | None:
    """Get the active clarify session ID."""
    session_file = _get_session_file(cwd)
    if not session_file.exists():
        return None

    try:
        data = json.loads(session_file.read_text())
        return data.get("session_id")
    except (json.JSONDecodeError, OSError):
        return None


def _clear_active_session(cwd: Path) -> None:
    """Clear the active clarify session."""
    session_file = _get_session_file(cwd)
    if session_file.exists():
        session_file.unlink()


def _build_keyboard(session_id: str, options: list[str]) -> dict[str, Any]:
    """Build inline keyboard with option buttons and skip.

    Args:
        session_id: Session ID for callback routing
        options: List of answer options

    Returns:
        Telegram reply_markup dict with inline_keyboard
    """
    buttons = []

    # Add numbered option buttons (one per row)
    for i, option in enumerate(options):
        # Truncate long options for button text
        label = option if len(option) <= 40 else option[:37] + "..."
        buttons.append(
            [
                {
                    "text": f"{i + 1}. {label}",
                    "callback_data": f"{CLARIFY_CALLBACK_PREFIX}{session_id}:{i}",
                }
            ]
        )

    # Add skip button
    buttons.append(
        [
            {
                "text": "Skip this question",
                "callback_data": f"{CLARIFY_CALLBACK_PREFIX}{session_id}:skip",
            }
        ]
    )

    return {"inline_keyboard": buttons}


async def send_question(
    ctx: CommandContext,
    session: ClarifySession,
    cwd: Path,
) -> None:
    """Send the current question with inline keyboard buttons.

    Also accepts text replies as fallback (number, 'skip', or custom text).
    """
    question = session.current_question()
    if not question:
        return

    # Build message text (Telegram HTML format)
    progress = session.progress_text()
    question_text = question.get("question", "")
    context = question.get("context", "")

    # Use HTML format for Telegram compatibility
    lines = [f"<b>[{progress}] {question_text}</b>"]

    if context:
        lines.append(f"\n<i>{context}</i>")

    lines.append("")
    lines.append("<i>Reply with a number (1, 2, 3...), 'skip', or your own answer.</i>")

    # Build keyboard
    options = question.get("options", [])
    keyboard = _build_keyboard(session.id, options)

    # Send with keyboard
    message = RenderedMessage(
        text="\n".join(lines),
        extra={"reply_markup": keyboard, "parse_mode": "HTML"},
    )
    await ctx.executor.send(message)

    # Track this as the active session (for text reply fallback)
    _save_active_session(cwd, session.id)


async def handle_clarify_response(
    ctx: CommandContext,
    response_text: str,
    cwd: Path,
) -> CommandResult | None:
    """Handle a text response to an active clarify session.

    This is the fallback for when users reply with text instead of buttons.

    Args:
        ctx: Command context
        response_text: User's text reply
        cwd: Working directory

    Returns:
        CommandResult or None
    """
    # Initialize managers
    flow = ClarifyFlow(cwd / ".ralph")
    prd_manager = PRDManager(cwd / "prd.json")

    # Get active session
    session_id = _get_active_session_id(cwd)
    if not session_id:
        return None  # No active session

    session = flow.get_session(session_id)
    if not session:
        _clear_active_session(cwd)
        return CommandResult(text="Session expired. Start a new /ralph prd clarify.")

    # Get current question for context
    question = session.current_question()
    options = question.get("options", []) if question else []

    # Parse response
    response_lower = response_text.strip().lower()

    if response_lower == "skip":
        has_more = session.skip_question()
        await ctx.executor.send("Skipped.")
    else:
        # Try to parse as number
        try:
            idx = int(response_text.strip())
            if 1 <= idx <= len(options):
                answer = options[idx - 1]  # Convert to 0-based index
                has_more = session.record_answer(answer)
                await ctx.executor.send(f"Got it: {answer}")
            else:
                # Number out of range - treat as custom answer
                has_more = session.record_answer(response_text.strip())
                await ctx.executor.send(f"Got it: {response_text.strip()}")
        except ValueError:
            # Not a number - treat as custom answer
            has_more = session.record_answer(response_text.strip())
            await ctx.executor.send(f"Got it: {response_text.strip()}")

    # Update session
    flow.update_session(session)

    if has_more:
        # Send next question
        await send_question(ctx, session, cwd)
        return None
    else:
        # Clear active session before completing
        _clear_active_session(cwd)
        # Session complete - use LLM to generate/enhance PRD with answers
        return await _complete_session(ctx, session, flow, prd_manager, cwd)


async def handle_clarify_callback(
    ctx: CommandContext,
    session_id: str,
    answer_index: str,
    cwd: Path,
) -> CommandResult | None:
    """Handle a callback from an inline keyboard button.

    Args:
        ctx: Command context
        session_id: The clarify session ID
        answer_index: Either a number index or "skip"
        cwd: Project working directory (resolved by backend)

    Returns:
        CommandResult or None
    """

    # Initialize managers
    flow = ClarifyFlow(cwd / ".ralph")
    prd_manager = PRDManager(cwd / "prd.json")

    # Get session
    session = flow.get_session(session_id)
    if not session:
        _clear_active_session(cwd)
        return CommandResult(text="Session expired. Start a new /ralph prd clarify.")

    # Get current question for context
    question = session.current_question()
    options = question.get("options", []) if question else []

    # Record answer
    if answer_index == "skip":
        has_more = session.skip_question()
        await ctx.executor.send("Skipped.")
    else:
        try:
            idx = int(answer_index)
            if 0 <= idx < len(options):
                answer = options[idx]
                has_more = session.record_answer(answer)
                await ctx.executor.send(f"Got it: {answer}")
            else:
                has_more = session.skip_question()
        except ValueError:
            has_more = session.skip_question()

    # Update session
    flow.update_session(session)

    if has_more:
        # Send next question
        await send_question(ctx, session, cwd)
        return None
    else:
        # Clear active session before completing
        _clear_active_session(cwd)
        # Session complete - use LLM to generate/enhance PRD with answers
        return await _complete_session(ctx, session, flow, prd_manager, cwd)


async def _complete_session(
    ctx: CommandContext,
    session: ClarifySession,
    flow: ClarifyFlow,
    prd_manager: PRDManager,
    cwd: Path,
) -> CommandResult:
    """Complete a clarify session by generating stories from answers.

    Uses LLM to analyze answers and generate appropriate user stories.
    """
    await ctx.executor.send("Generating stories from your answers...")

    # Load or create PRD
    if session.mode == "enhance" and prd_manager.exists():
        prd = prd_manager.load()
    else:
        # Create mode - get project info from session
        topic = session.topic
        description = session.answers.pop("_description", "")
        prd = PRD(project_name=topic, description=description)

    # Use LLM to generate stories from answers
    analyzer = LLMAnalyzer(ctx.executor, cwd=cwd)

    # Filter out internal keys from answers
    user_answers = {k: v for k, v in session.answers.items() if not k.startswith("_")}

    result = await analyzer.analyze(
        prd_json=prd.model_dump_json(),
        mode=session.mode,
        topic=session.topic,
        focus=session.focus,
        answers=user_answers,
    )

    # Add suggested stories (avoiding duplicates)
    added_count = 0
    existing_titles = {s.title.lower() for s in prd.stories}

    for story in result.suggested_stories:
        if story.title.lower() not in existing_titles:
            prd.add_story(
                title=story.title,
                description=story.description,
                acceptance_criteria=story.acceptance_criteria,
                priority=story.priority,
            )
            existing_titles.add(story.title.lower())
            added_count += 1

    # Save PRD
    prd_manager.save(prd)

    # Clean up session
    flow.delete_session(session.id)

    # Build response (plain text - no markdown issues)
    if session.mode == "enhance":
        if added_count > 0:
            new_stories = [f"  {s.id}. {s.title}" for s in prd.stories[-added_count:]]
            new_stories_text = "\n".join(new_stories)
            return CommandResult(
                text=f"PRD enhanced for {prd.project_name}\n\n"
                f"{result.analysis}\n\n"
                f"Added {added_count} new stories:\n{new_stories_text}\n\n"
                f"Total: {len(prd.stories)} stories\n"
                f"Run /ralph start to continue!"
            )
        else:
            return CommandResult(
                text=f"PRD reviewed for {prd.project_name}\n\n"
                f"{result.analysis}\n\n"
                f"No new stories needed based on your answers.\n"
                f"Total: {len(prd.stories)} stories\n"
                f"Run /ralph start to continue!"
            )
    else:
        # Create mode
        stories_text = "\n".join(f"  {s.id}. {s.title}" for s in prd.stories[:5])
        if len(prd.stories) > 5:
            stories_text += f"\n  ... and {len(prd.stories) - 5} more"

        return CommandResult(
            text=f"PRD created for {prd.project_name}\n\n"
            f"{result.analysis}\n\n"
            f"Generated {len(prd.stories)} user stories:\n{stories_text}\n\n"
            f"PRD saved to prd.json\n"
            f"Run /ralph start to begin implementation!"
        )
