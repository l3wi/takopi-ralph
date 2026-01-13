"""LLM-powered PRD analyzer using Takopi's engine system.

Replaces the rule-based PRDAnalyzer with dynamic LLM analysis.
Uses Takopi's CommandExecutor to run prompts through the configured engine.

Note: Uses file-based output (writes to .ralph/analysis.json) because
takopi's capture mode doesn't capture raw LLM output - it captures
presenter-formatted status messages like "done · claude · 51s".
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from .prompt_loader import build_user_prompt, get_system_prompt

if TYPE_CHECKING:
    from takopi.api import CommandExecutor

logger = logging.getLogger(__name__)

# Output file for analysis results (relative to cwd)
ANALYSIS_OUTPUT_FILE = ".ralph/analysis.json"


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

    The analyzer instructs the LLM to write its JSON response to a file,
    then reads that file to get the structured output. This works around
    takopi's capture mode limitations.
    """

    def __init__(self, executor: CommandExecutor, cwd: Path | None = None):
        """Initialize the analyzer.

        Args:
            executor: Takopi CommandExecutor for running prompts
            cwd: Working directory for output file. If None, uses current dir.
        """
        self.executor = executor
        self.cwd = cwd or Path.cwd()

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

        # Determine output file path
        output_path = self.cwd / ANALYSIS_OUTPUT_FILE
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Delete existing output file to ensure we get fresh results
        if output_path.exists():
            output_path.unlink()

        # Build prompt that instructs LLM to write JSON to file
        full_prompt = f"""{system_prompt}

---

{user_prompt}

---

**IMPORTANT**: Write your JSON response to: `{output_path}`

Use the Write tool to create the file with your JSON analysis result.
Do NOT just print the JSON - you MUST write it to the file.
The file should contain ONLY the raw JSON object, no markdown formatting."""

        # Run through Takopi's engine with capture mode
        # This runs the engine silently (no chat output) but still executes tools
        # The LLM will write its analysis to the output file
        await self.executor.run_one(
            RunRequest(prompt=full_prompt),
            mode="capture",
        )

        # Read the output file
        return self._read_output_file(output_path)

    def _read_output_file(self, path: Path) -> AnalysisResult:
        """Read and parse the analysis output file."""
        if not path.exists():
            logger.warning("Analysis output file not found: %s", path)
            return AnalysisResult(
                analysis="LLM did not write analysis output file",
                questions=[],
                suggested_stories=[],
            )

        try:
            content = path.read_text().strip()
            logger.debug("Read analysis output: %s", content[:200])

            # Try to parse as JSON
            data = json.loads(content)
            return self._dict_to_result(data)

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse analysis JSON: %s", e)
            return AnalysisResult(
                analysis=f"Failed to parse analysis JSON: {e}",
                questions=[],
                suggested_stories=[],
            )
        except OSError as e:
            logger.warning("Failed to read analysis file: %s", e)
            return AnalysisResult(
                analysis=f"Failed to read analysis file: {e}",
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
    cwd: Path | None = None,
    **kwargs: Any,
) -> AnalysisResult:
    """Analyze PRD using Takopi's engine.

    Args:
        executor: Takopi CommandExecutor
        prd_json: Current PRD as JSON string
        mode: "create" or "enhance"
        cwd: Working directory for output file
        **kwargs: Additional arguments (topic, description, focus, answers)

    Returns:
        AnalysisResult with analysis, questions, and suggested stories
    """
    analyzer = LLMAnalyzer(executor, cwd=cwd)
    return await analyzer.analyze(prd_json, mode, **kwargs)
