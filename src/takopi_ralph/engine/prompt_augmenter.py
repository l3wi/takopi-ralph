"""Prompt augmentation for Ralph loops.

Adds Ralph instructions to Claude prompts including
the RALPH_STATUS block requirement.
"""

from __future__ import annotations

from ..prd import PRD, UserStory

RALPH_STATUS_INSTRUCTIONS = '''
## RALPH STATUS REPORTING (CRITICAL)

At the END of your response, you MUST include this status block:

```
---RALPH_STATUS---
STATUS: IN_PROGRESS | COMPLETE | BLOCKED
TASKS_COMPLETED_THIS_LOOP: <number>
FILES_MODIFIED: <number>
TESTS_STATUS: PASSING | FAILING | NOT_RUN
WORK_TYPE: IMPLEMENTATION | TESTING | DOCUMENTATION | REFACTORING
EXIT_SIGNAL: false | true
RECOMMENDATION: <one-line summary of what to do next>
---END_RALPH_STATUS---
```

### When to set EXIT_SIGNAL: true
Set EXIT_SIGNAL to true when ALL of these conditions are met:
1. All tasks in prd.json are marked complete
2. All tests are passing (or no tests exist)
3. No errors in the last execution
4. You have nothing meaningful left to implement

### What NOT to do:
- Do NOT continue with busy work when EXIT_SIGNAL should be true
- Do NOT run tests repeatedly without implementing new features
- Do NOT refactor code that is already working fine
- Do NOT add features not in the specifications
'''


def build_ralph_prompt(
    user_prompt: str,
    prd: PRD | None = None,
    current_story: UserStory | None = None,
    loop_number: int = 0,
    circuit_state: str = "CLOSED",
) -> str:
    """Build an augmented prompt with Ralph instructions.

    Args:
        user_prompt: Original user prompt
        prd: Current PRD (if loaded)
        current_story: Current story to work on
        loop_number: Current loop iteration
        circuit_state: Current circuit breaker state

    Returns:
        Augmented prompt with Ralph instructions
    """
    parts = []

    # Context header
    parts.append(f"# Ralph Loop #{loop_number}")
    parts.append(f"Circuit Breaker: {circuit_state}")
    parts.append("")

    # PRD context
    if prd:
        parts.append("## Project Context")
        parts.append(f"Project: {prd.project_name}")
        parts.append(f"Progress: {prd.progress_summary()}")
        parts.append("")

    # Current story
    if current_story:
        parts.append("## Current Task")
        parts.append(f"Story #{current_story.id}: {current_story.title}")
        parts.append(f"Description: {current_story.description}")
        if current_story.acceptance_criteria:
            parts.append("Acceptance Criteria:")
            for criterion in current_story.acceptance_criteria:
                parts.append(f"  - {criterion}")
        parts.append("")

    # User prompt
    parts.append("## Your Task")
    parts.append(user_prompt)
    parts.append("")

    # Ralph instructions
    parts.append(RALPH_STATUS_INSTRUCTIONS)

    return "\n".join(parts)


def build_continuation_prompt(
    loop_number: int,
    prd: PRD | None = None,
    current_story: UserStory | None = None,
    circuit_state: str = "CLOSED",
) -> str:
    """Build a continuation prompt for the next loop iteration.

    Args:
        loop_number: Current loop iteration
        prd: Current PRD
        current_story: Current story to work on
        circuit_state: Current circuit breaker state

    Returns:
        Continuation prompt
    """
    parts = []

    parts.append(f"# Ralph Loop #{loop_number} - Continuation")
    parts.append(f"Circuit Breaker: {circuit_state}")
    parts.append("")

    if prd:
        parts.append(f"Progress: {prd.progress_summary()}")
        parts.append("")

    if current_story:
        parts.append(f"Continue working on Story #{current_story.id}: {current_story.title}")
        parts.append("")
        parts.append("Focus on ONE task at a time. When complete, update the story status.")
    else:
        parts.append(
            "All stories appear complete. Verify everything works "
            "and set EXIT_SIGNAL: true if done."
        )

    parts.append("")
    parts.append(RALPH_STATUS_INSTRUCTIONS)

    return "\n".join(parts)
