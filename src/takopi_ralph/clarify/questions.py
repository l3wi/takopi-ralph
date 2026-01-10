"""Question categories for /ralph clarify flow."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ClarifyCategory(str, Enum):
    """Categories of clarifying questions."""

    CORE_REQUIREMENTS = "core_requirements"
    USERS_CONTEXT = "users_context"
    INTEGRATION_POINTS = "integration_points"
    EDGE_CASES = "edge_cases"
    QUALITY_ATTRIBUTES = "quality_attributes"


@dataclass
class ClarifyQuestion:
    """A single clarifying question."""

    id: str
    category: ClarifyCategory
    question: str
    options: list[str]
    allows_custom: bool = True


# Predefined questions for each category
QUESTIONS: list[ClarifyQuestion] = [
    # Core Requirements
    ClarifyQuestion(
        id="mvp_scope",
        category=ClarifyCategory.CORE_REQUIREMENTS,
        question="What is the minimum viable version?",
        options=["Basic CRUD", "Full feature set", "Prototype only", "Production ready"],
    ),
    ClarifyQuestion(
        id="out_of_scope",
        category=ClarifyCategory.CORE_REQUIREMENTS,
        question="What is explicitly out of scope?",
        options=["Mobile app", "Admin panel", "API", "Authentication", "Nothing specific"],
    ),
    ClarifyQuestion(
        id="tech_stack",
        category=ClarifyCategory.CORE_REQUIREMENTS,
        question="What is the tech stack?",
        options=["Next.js + TypeScript", "Python + FastAPI", "Node.js + Express", "Other"],
    ),
    # Users Context
    ClarifyQuestion(
        id="primary_user",
        category=ClarifyCategory.USERS_CONTEXT,
        question="Who is the primary user?",
        options=["Developers", "End users", "Admins", "All of the above"],
    ),
    ClarifyQuestion(
        id="user_skill",
        category=ClarifyCategory.USERS_CONTEXT,
        question="What is their technical skill level?",
        options=["Beginner", "Intermediate", "Expert", "Mixed"],
    ),
    # Integration Points
    ClarifyQuestion(
        id="external_apis",
        category=ClarifyCategory.INTEGRATION_POINTS,
        question="Any external APIs or services to integrate?",
        options=["None", "Database", "Third-party APIs", "Payment systems", "Multiple"],
    ),
    ClarifyQuestion(
        id="auth_method",
        category=ClarifyCategory.INTEGRATION_POINTS,
        question="What authentication method?",
        options=["None needed", "Simple password", "OAuth/SSO", "JWT tokens"],
    ),
    # Edge Cases
    ClarifyQuestion(
        id="error_handling",
        category=ClarifyCategory.EDGE_CASES,
        question="How should errors be handled?",
        options=["Simple messages", "Detailed logging", "User-friendly UI", "All of the above"],
    ),
    ClarifyQuestion(
        id="offline_support",
        category=ClarifyCategory.EDGE_CASES,
        question="Is offline support needed?",
        options=["No", "Yes - basic caching", "Yes - full offline mode"],
    ),
    # Quality Attributes
    ClarifyQuestion(
        id="testing_level",
        category=ClarifyCategory.QUALITY_ATTRIBUTES,
        question="What level of testing is expected?",
        options=["Minimal", "Unit tests", "Integration tests", "Full coverage"],
    ),
    ClarifyQuestion(
        id="performance",
        category=ClarifyCategory.QUALITY_ATTRIBUTES,
        question="Are there performance requirements?",
        options=["No specific", "Fast load times", "Handle high traffic", "Real-time"],
    ),
]


def get_questions_by_category(category: ClarifyCategory) -> list[ClarifyQuestion]:
    """Get all questions for a specific category."""
    return [q for q in QUESTIONS if q.category == category]


def get_question_by_id(question_id: str) -> ClarifyQuestion | None:
    """Get a question by its ID."""
    for q in QUESTIONS:
        if q.id == question_id:
            return q
    return None


def get_all_questions() -> list[ClarifyQuestion]:
    """Get all questions in order."""
    return QUESTIONS.copy()
