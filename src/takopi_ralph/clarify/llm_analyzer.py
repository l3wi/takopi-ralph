"""LLM-powered PRD analyzer using Takopi's engine system.

Replaces the rule-based PRDAnalyzer with dynamic LLM analysis.
Uses Takopi's CommandExecutor to run prompts through the configured engine.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from .prompt_loader import build_user_prompt, get_system_prompt

if TYPE_CHECKING:
    from takopi.api import CommandExecutor


class PRDQuestion(BaseModel):
    """A clarifying question for the user."""

    question: str
    options: list[str]
    context: str = ""


class SuggestedStory(BaseModel):
    """A story suggested by the LLM."""

    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    priority: int = 1


class AnalysisResult(BaseModel):
    """Result from LLM PRD analysis."""

    analysis: str
    questions: list[PRDQuestion] = Field(default_factory=list)
    suggested_stories: list[SuggestedStory] = Field(default_factory=list)


class LLMAnalyzer:
    """LLM-powered PRD analyzer using Takopi's engine system.

    Uses the configured Takopi engine (e.g., Claude) to dynamically
    analyze PRDs, generate questions, and suggest user stories.
    """

    def __init__(self, executor: CommandExecutor):
        """Initialize the analyzer.

        Args:
            executor: Takopi CommandExecutor for running prompts
        """
        self.executor = executor

    async def analyze(
        self,
        prd_json: str,
        mode: str,
        topic: str | None = None,
        description: str | None = None,
        focus: str | None = None,
        answers: dict[str, str] | None = None,
    ) -> AnalysisResult:
        """Analyze PRD and return questions/stories.

        Args:
            prd_json: Current PRD as JSON string
            mode: "create" or "enhance"
            topic: Project topic (for create mode)
            description: Project description (for create mode)
            focus: Focus area (for enhance mode)
            answers: User's answers to previous questions

        Returns:
            AnalysisResult with analysis, questions, and suggested stories
        """
        # Import here to avoid circular imports
        from takopi.api import RunRequest

        system_prompt = get_system_prompt()
        user_prompt = build_user_prompt(
            mode=mode,
            prd_json=prd_json,
            topic=topic,
            description=description,
            focus=focus,
            answers=answers,
        )

        # Combine system + user prompt for the engine
        # Most engines expect a single prompt, so we combine them
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

        # Run through Takopi's engine with capture mode (don't emit to chat)
        result = await self.executor.run_one(
            RunRequest(prompt=full_prompt),
            mode="capture",
        )

        # Extract the response text
        response_text = ""
        if result.message:
            msg = result.message
            response_text = msg.text if hasattr(msg, "text") else str(msg)

        return self._parse_response(response_text)

    def _parse_response(self, text: str) -> AnalysisResult:
        """Parse LLM response into AnalysisResult.

        Handles both clean JSON and JSON embedded in markdown code blocks.
        """
        if not text:
            return AnalysisResult(
                analysis="No response from LLM",
                questions=[],
                suggested_stories=[],
            )

        # Try to extract JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if json_match:
            json_text = json_match.group(1)
        else:
            # Try to find raw JSON object
            json_match = re.search(r"\{[\s\S]*\}", text)
            if json_match:
                json_text = json_match.group(0)
            else:
                # No JSON found, return empty result with the text as analysis
                return AnalysisResult(
                    analysis=text[:500],
                    questions=[],
                    suggested_stories=[],
                )

        try:
            data = json.loads(json_text)
            return self._dict_to_result(data)
        except json.JSONDecodeError:
            # JSON parse failed, return the text as analysis
            return AnalysisResult(
                analysis=f"Failed to parse LLM response: {text[:200]}",
                questions=[],
                suggested_stories=[],
            )

    def _dict_to_result(self, data: dict[str, Any]) -> AnalysisResult:
        """Convert parsed dict to AnalysisResult."""
        questions = []
        for q in data.get("questions", []):
            if isinstance(q, dict) and "question" in q and "options" in q:
                questions.append(
                    PRDQuestion(
                        question=q["question"],
                        options=q["options"],
                        context=q.get("context", ""),
                    )
                )

        stories = []
        for s in data.get("suggested_stories", []):
            if isinstance(s, dict) and "title" in s:
                stories.append(
                    SuggestedStory(
                        title=s["title"],
                        description=s.get("description", ""),
                        acceptance_criteria=s.get("acceptance_criteria", []),
                        priority=s.get("priority", 1),
                    )
                )

        return AnalysisResult(
            analysis=data.get("analysis", ""),
            questions=questions,
            suggested_stories=stories,
        )


# Convenience function for one-off analysis
async def analyze_prd(
    executor: CommandExecutor,
    prd_json: str,
    mode: str,
    **kwargs: Any,
) -> AnalysisResult:
    """Analyze PRD using Takopi's engine.

    Args:
        executor: Takopi CommandExecutor
        prd_json: Current PRD as JSON string
        mode: "create" or "enhance"
        **kwargs: Additional arguments (topic, description, focus, answers)

    Returns:
        AnalysisResult with analysis, questions, and suggested stories
    """
    analyzer = LLMAnalyzer(executor)
    return await analyzer.analyze(prd_json, mode, **kwargs)
