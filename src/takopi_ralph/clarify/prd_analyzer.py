"""PRD gap analyzer for clarify flow.

Analyzes existing PRDs to identify areas needing improvement.
"""

from __future__ import annotations

from enum import Enum

from ..prd import PRD
from .questions import QUESTIONS, ClarifyQuestion


class PRDGap(str, Enum):
    """Types of gaps that can be identified in a PRD."""

    FEW_STORIES = "few_stories"
    NO_TESTING = "no_testing"
    NO_ERROR_HANDLING = "no_error_handling"
    NO_AUTH = "no_auth"
    MISSING_ACCEPTANCE_CRITERIA = "missing_acceptance_criteria"
    NO_SETUP = "no_setup"


# Map gaps to relevant question IDs
GAP_TO_QUESTIONS: dict[PRDGap, list[str]] = {
    PRDGap.FEW_STORIES: ["mvp_scope", "tech_stack"],
    PRDGap.NO_TESTING: ["testing_level"],
    PRDGap.NO_ERROR_HANDLING: ["error_handling"],
    PRDGap.NO_AUTH: ["auth_method"],
    PRDGap.MISSING_ACCEPTANCE_CRITERIA: ["mvp_scope"],
    PRDGap.NO_SETUP: ["tech_stack"],
}

# Keywords that suggest auth is needed
AUTH_KEYWORDS = ["user", "account", "login", "profile", "member", "session"]

# Keywords that suggest testing stories exist
TESTING_KEYWORDS = ["test", "testing", "spec", "coverage", "unit", "integration"]

# Keywords that suggest error handling exists
ERROR_KEYWORDS = ["error", "exception", "handling", "validation", "fallback"]

# Keywords that suggest setup/init stories exist
SETUP_KEYWORDS = ["setup", "initialize", "configuration", "install", "scaffold"]

# Keywords for focused clarify mode
FOCUS_KEYWORDS: dict[str, list[str]] = {
    "auth_method": ["auth", "oauth", "login", "sso", "jwt", "authentication", "session"],
    "testing_level": ["test", "testing", "coverage", "spec", "unit", "integration"],
    "error_handling": ["error", "exception", "handling", "validation", "fallback"],
    "tech_stack": ["stack", "framework", "next", "react", "python", "node", "typescript"],
    "external_apis": ["api", "integration", "service", "third-party", "external"],
    "performance": ["performance", "speed", "optimization", "cache", "fast"],
    "mvp_scope": ["mvp", "scope", "feature", "functionality", "extend"],
}


class PRDAnalyzer:
    """Analyzes PRDs to identify gaps and improvement opportunities."""

    def analyze(self, prd: PRD) -> list[PRDGap]:
        """Analyze PRD and return list of identified gaps.

        Args:
            prd: The PRD to analyze

        Returns:
            List of PRDGap values indicating areas needing improvement
        """
        gaps: list[PRDGap] = []

        # Check story count
        if prd.total_count() < 3:
            gaps.append(PRDGap.FEW_STORIES)

        # Collect all story text for keyword analysis
        story_text = " ".join(
            f"{s.title} {s.description}".lower() for s in prd.stories
        )

        # Check for testing stories
        if not any(kw in story_text for kw in TESTING_KEYWORDS):
            gaps.append(PRDGap.NO_TESTING)

        # Check for error handling stories
        if not any(kw in story_text for kw in ERROR_KEYWORDS):
            gaps.append(PRDGap.NO_ERROR_HANDLING)

        # Check for setup stories
        if not any(kw in story_text for kw in SETUP_KEYWORDS):
            gaps.append(PRDGap.NO_SETUP)

        # Check acceptance criteria
        stories_without_criteria = [s for s in prd.stories if not s.acceptance_criteria]
        if len(stories_without_criteria) > len(prd.stories) // 2:
            gaps.append(PRDGap.MISSING_ACCEPTANCE_CRITERIA)

        # Check for auth if description suggests users
        desc = (prd.description or "").lower()
        if (
            any(kw in desc for kw in AUTH_KEYWORDS)
            and not any(kw in story_text for kw in ["auth", "login", "session"])
        ):
            gaps.append(PRDGap.NO_AUTH)

        return gaps

    def get_questions_for_gaps(self, gaps: list[PRDGap]) -> list[ClarifyQuestion]:
        """Get relevant clarify questions for identified gaps.

        Args:
            gaps: List of PRDGap values

        Returns:
            List of ClarifyQuestion objects to ask
        """
        question_ids: set[str] = set()

        for gap in gaps:
            if gap in GAP_TO_QUESTIONS:
                question_ids.update(GAP_TO_QUESTIONS[gap])

        # Get questions in original order
        return [q for q in QUESTIONS if q.id in question_ids]


def get_questions_for_focus(focus: str) -> list[ClarifyQuestion]:
    """Get relevant questions based on focus text.

    Args:
        focus: User-provided focus text (e.g., "Add OAuth to API")

    Returns:
        List of relevant ClarifyQuestion objects
    """
    focus_lower = focus.lower()
    matching_ids: set[str] = set()

    # Find matching question categories based on keywords
    for question_id, keywords in FOCUS_KEYWORDS.items():
        if any(kw in focus_lower for kw in keywords):
            matching_ids.add(question_id)

    # If no specific matches, use general questions
    if not matching_ids:
        matching_ids = {"mvp_scope", "tech_stack"}

    return [q for q in QUESTIONS if q.id in matching_ids]
