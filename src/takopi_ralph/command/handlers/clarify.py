"""Handler for clarify flow with inline keyboard interactions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from takopi.api import CommandContext, CommandResult
from takopi.transport import RenderedMessage

from ...clarify import ClarifyFlow, ClarifySession
from ...clarify.llm_analyzer import LLMAnalyzer
from ...prd import PRD, PRDManager

# Callback data prefix for clarify responses (under /ralph prd clarify)
CLARIFY_CALLBACK_PREFIX = "ralph:prd:clarify:"


def build_clarify_keyboard(
    session_id: str,
    options: list[str],
    include_skip: bool = True,
) -> dict[str, Any]:
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
        buttons.append(
            [
                {
                    "text": option,
                    "callback_data": f"{CLARIFY_CALLBACK_PREFIX}{session_id}:{i}",
                }
            ]
        )

    # Add skip button
    if include_skip:
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
) -> None:
    """Send the current question with inline keyboard.

    Works with the new LLM-generated question format (dict with question, options, context).
    """
    question = session.current_question()
    if not question:
        return

    # Build message
    progress = session.progress_text()
    question_text = question.get("question", "")
    context = question.get("context", "")

    text = f"**[{progress}] {question_text}**"
    if context:
        text += f"\n\n_{context}_"

    # Build keyboard
    options = question.get("options", [])
    keyboard = build_clarify_keyboard(session.id, options)

    # Send with keyboard
    message = RenderedMessage(
        text=text,
        extra={"reply_markup": keyboard},
    )
    await ctx.executor.send(message)


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
        return CommandResult(text="Session expired. Start a new `/ralph prd clarify`.")

    # Get current question for context
    question = session.current_question()

    # Record answer
    if answer_index == "skip":
        has_more = session.skip_question()
    else:
        try:
            idx = int(answer_index)
            options = question.get("options", []) if question else []
            if question and 0 <= idx < len(options):
                answer = options[idx]
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
        # Session complete - use LLM to generate/enhance PRD with answers
        return await _complete_session(ctx, session, flow, prd_manager)


async def _complete_session(
    ctx: CommandContext,
    session: ClarifySession,
    flow: ClarifyFlow,
    prd_manager: PRDManager,
) -> CommandResult:
    """Complete a clarify session by generating stories from answers.

    Uses LLM to analyze answers and generate appropriate user stories.
    """
    await ctx.executor.send("**Generating stories from your answers...**")

    # Load or create PRD
    if session.mode == "enhance" and prd_manager.exists():
        prd = prd_manager.load()
    else:
        # Create mode - get project info from session
        topic = session.topic
        description = session.answers.pop("_description", "")
        prd = PRD(project_name=topic, description=description)

    # Use LLM to generate stories from answers
    analyzer = LLMAnalyzer(ctx.executor)

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

    # Build response
    if session.mode == "enhance":
        if added_count > 0:
            new_stories_text = "\n".join(f"  {s.id}. {s.title}" for s in prd.stories[-added_count:])
            return CommandResult(
                text=f"**PRD enhanced for {prd.project_name}**\n\n"
                f"{result.analysis}\n\n"
                f"Added {added_count} new stories:\n{new_stories_text}\n\n"
                f"Total: {len(prd.stories)} stories\n"
                f"Run `/ralph start` to continue!"
            )
        else:
            return CommandResult(
                text=f"**PRD reviewed for {prd.project_name}**\n\n"
                f"{result.analysis}\n\n"
                f"No new stories needed based on your answers.\n"
                f"Total: {len(prd.stories)} stories\n"
                f"Run `/ralph start` to continue!"
            )
    else:
        # Create mode
        stories_text = "\n".join(f"  {s.id}. {s.title}" for s in prd.stories[:5])
        if len(prd.stories) > 5:
            stories_text += f"\n  ... and {len(prd.stories) - 5} more"

        return CommandResult(
            text=f"**PRD created for {prd.project_name}**\n\n"
            f"{result.analysis}\n\n"
            f"Generated {len(prd.stories)} user stories:\n{stories_text}\n\n"
            f"PRD saved to `prd.json`\n"
            f"Run `/ralph start` to begin implementation!"
        )
