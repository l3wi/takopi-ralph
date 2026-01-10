"""Handler for /ralph clarify command with inline keyboard flow."""

from __future__ import annotations

from pathlib import Path

from takopi.api import CommandContext, CommandResult
from takopi.transport import RenderedMessage

from ...clarify import (
    ClarifyFlow,
    ClarifySession,
    build_prd_from_session,
    enhance_prd_from_session,
)
from ...clarify.questions import get_all_questions
from ...prd import PRDManager

# Callback data prefix for clarify responses (under /ralph prd clarify)
CLARIFY_CALLBACK_PREFIX = "ralph:prd:clarify:"


def build_clarify_keyboard(
    session_id: str,
    options: list[str],
    include_skip: bool = True,
) -> dict:
    """Build an inline keyboard for a clarify question.

    Args:
        session_id: Session ID for callback routing
        options: List of answer options
        include_skip: Whether to include a skip button

    Returns:
        Telegram reply_markup dict with inline_keyboard
    """
    buttons = []

    # Add option buttons (one per row for clarity)
    for i, option in enumerate(options):
        buttons.append([{
            "text": option,
            "callback_data": f"{CLARIFY_CALLBACK_PREFIX}{session_id}:{i}",
        }])

    # Add skip button
    if include_skip:
        buttons.append([{
            "text": "Skip this question",
            "callback_data": f"{CLARIFY_CALLBACK_PREFIX}{session_id}:skip",
        }])

    return {"inline_keyboard": buttons}


async def send_question(
    ctx: CommandContext,
    session: ClarifySession,
) -> None:
    """Send the current question with inline keyboard."""
    question = session.current_question()
    if not question:
        return

    # Build message
    progress = session.progress_text()
    text = f"**[{progress}] {question.question}**"

    # Build keyboard
    keyboard = build_clarify_keyboard(session.id, question.options)

    # Send with keyboard
    message = RenderedMessage(
        text=text,
        extra={"reply_markup": keyboard},
    )
    await ctx.executor.send(message)


async def handle_clarify(ctx: CommandContext) -> CommandResult | None:
    """Handle /ralph clarify <topic> command.

    Starts an interactive requirements gathering flow using inline keyboards.
    """
    cwd = Path.cwd()
    args = ctx.args[1:] if len(ctx.args) > 1 else []

    if not args:
        return CommandResult(
            text="Usage: `/ralph clarify <topic>`\n"
            "Example: `/ralph clarify Task management app`"
        )

    topic = " ".join(args)

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


async def handle_clarify_callback(
    ctx: CommandContext,
    session_id: str,
    answer_index: str,
) -> CommandResult | None:
    """Handle a callback from a clarify inline keyboard button.

    Args:
        ctx: Command context
        session_id: The clarify session ID
        answer_index: Either a number index or "skip"

    Returns:
        CommandResult or None
    """
    cwd = Path.cwd()

    # Initialize managers
    flow = ClarifyFlow(cwd / ".ralph")
    prd_manager = PRDManager(cwd / "prd.json")

    # Get session
    session = flow.get_session(session_id)
    if not session:
        return CommandResult(text="Session expired. Start a new `/ralph clarify`.")

    # Get current question for context
    question = session.current_question()

    # Record answer
    if answer_index == "skip":
        has_more = session.skip_question()
    else:
        try:
            idx = int(answer_index)
            if question and 0 <= idx < len(question.options):
                answer = question.options[idx]
                has_more = session.record_answer(answer)

                # Acknowledge the answer
                await ctx.executor.send(f"Got it: *{answer}*")
            else:
                has_more = session.skip_question()
        except ValueError:
            has_more = session.skip_question()

    # Update session
    flow.update_session(session)

    if has_more:
        # Send next question
        await send_question(ctx, session)
        return None
    else:
        # Session complete - build or enhance PRD
        if session.mode == "enhance" and prd_manager.exists():
            # Enhance existing PRD
            existing_prd = prd_manager.load()
            old_count = len(existing_prd.stories)
            prd = enhance_prd_from_session(existing_prd, session)
            new_count = len(prd.stories) - old_count
            prd_manager.save(prd)

            # Clean up session
            flow.delete_session(session_id)

            if new_count > 0:
                new_stories_text = "\n".join(
                    f"  {s.id}. {s.title}" for s in prd.stories[-new_count:]
                )
                return CommandResult(
                    text=f"**PRD enhanced for {prd.project_name}**\n\n"
                    f"Added {new_count} new stories:\n{new_stories_text}\n\n"
                    f"Total: {len(prd.stories)} stories\n"
                    f"Run `/ralph start` to continue!"
                )
            else:
                return CommandResult(
                    text=f"**PRD reviewed for {prd.project_name}**\n\n"
                    f"No new stories needed based on your answers.\n"
                    f"Total: {len(prd.stories)} stories\n"
                    f"Run `/ralph start` to continue!"
                )
        else:
            # Create new PRD
            prd = build_prd_from_session(session)
            prd_manager.save(prd)

            # Clean up session
            flow.delete_session(session_id)

            # Send completion message
            stories_text = "\n".join(
                f"  {s.id}. {s.title}" for s in prd.stories[:5]
            )
            if len(prd.stories) > 5:
                stories_text += f"\n  ... and {len(prd.stories) - 5} more"

            return CommandResult(
                text=f"Requirements captured for **{prd.project_name}**\n\n"
                f"Generated {len(prd.stories)} user stories:\n{stories_text}\n\n"
                f"PRD saved to `prd.json`\n"
                f"Run `/ralph start` to begin implementation!"
            )
