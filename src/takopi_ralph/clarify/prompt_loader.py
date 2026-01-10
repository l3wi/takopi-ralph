"""Prompt template loader for LLM analyzer.

Loads prompt templates from the prompts/ folder and injects variables.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str, **variables: Any) -> str:
    """Load prompt template and inject variables.

    Args:
        name: Template name (without .txt extension)
        **variables: Variables to inject into template

    Returns:
        Rendered prompt string

    Example:
        load_prompt("create", topic="My App", prd_json="{}")
    """
    template_path = PROMPTS_DIR / f"{name}.txt"
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")

    template = template_path.read_text()
    return _render_template(template, variables)


def _render_template(template: str, variables: dict[str, Any]) -> str:
    """Render template with variable substitution.

    Supports:
    - {{variable}} - Simple substitution
    - Empty string if variable not provided
    """
    def replace_var(match: re.Match[str]) -> str:
        var_name = match.group(1)
        value = variables.get(var_name, "")
        if value is None:
            return ""
        return str(value)

    # Replace {{variable}} patterns
    pattern = r"\{\{(\w+)\}\}"
    return re.sub(pattern, replace_var, template)


def get_system_prompt() -> str:
    """Load the shared system prompt with PRD schema injected.

    Returns:
        System prompt string with schema information
    """
    # Build human-readable schema (hardcoded for clarity in prompts)
    schema = """A PRD (Product Requirements Document) has:
- project_name: string
- description: string
- created_at: datetime
- branch_name: string | null
- stories: array of UserStory

A UserStory has:
- id: int (auto-assigned, don't include in suggestions)
- title: string
- description: string
- acceptance_criteria: array of strings
- priority: int (1 = highest priority)
- passes: bool (completion status, always false for new stories)
- notes: string (optional)"""

    return load_prompt("system", prd_schema=schema)


def build_user_prompt(
    mode: str,
    prd_json: str,
    topic: str | None = None,
    description: str | None = None,
    focus: str | None = None,
    answers: dict[str, str] | None = None,
) -> str:
    """Build the user prompt based on mode and context.

    Args:
        mode: "create" or "enhance"
        prd_json: Current PRD as JSON string
        topic: Project topic (for create mode)
        description: Project description (for create mode)
        focus: Focus area (for enhance mode)
        answers: User's answers to previous questions

    Returns:
        Rendered user prompt string
    """
    # If we have answers, use the follow-up prompt
    if answers:
        answers_text = "\n".join(f"- {q}: {a}" for q, a in answers.items())
        return load_prompt("with_answers", answers=answers_text, prd_json=prd_json)

    # Create mode
    if mode == "create":
        desc_text = f"\n**Description:** {description}" if description else ""
        return load_prompt(
            "create", topic=topic or "Unknown", description=desc_text, prd_json=prd_json
        )

    # Enhance mode with focus
    if focus:
        return load_prompt("enhance_focused", focus=focus, prd_json=prd_json)

    # Enhance mode without focus
    return load_prompt("enhance", prd_json=prd_json)
