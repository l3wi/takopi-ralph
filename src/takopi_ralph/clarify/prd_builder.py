"""Build prd.json from clarify session answers."""

from __future__ import annotations

from datetime import UTC, datetime

from ..prd import PRD, UserStory
from .flow import ClarifySession


def build_prd_from_session(session: ClarifySession) -> PRD:
    """Generate a PRD with user stories from a clarify session.

    This function analyzes the answers and generates appropriate
    user stories based on the requirements gathered.
    """
    stories: list[UserStory] = []
    priority = 1

    # Analyze answers to generate stories
    answers = session.answers

    # Core setup story (always first)
    stories.append(
        UserStory(
            id=priority,
            title="Project Setup",
            description=f"Initialize {session.topic} project with basic structure",
            acceptance_criteria=[
                "Project structure created",
                "Dependencies installed",
                "Basic configuration in place",
            ],
            priority=priority,
        )
    )
    priority += 1

    # Tech stack specific setup
    tech_stack = answers.get("tech_stack", "")
    if "Next.js" in tech_stack or "TypeScript" in tech_stack:
        stories.append(
            UserStory(
                id=priority,
                title="TypeScript Configuration",
                description="Set up TypeScript with strict mode and proper types",
                acceptance_criteria=[
                    "tsconfig.json configured",
                    "No TypeScript errors",
                    "Proper module resolution",
                ],
                priority=priority,
            )
        )
        priority += 1

    # Authentication if needed
    auth_method = answers.get("auth_method", "")
    if auth_method and auth_method != "None needed":
        stories.append(
            UserStory(
                id=priority,
                title="User Authentication",
                description=f"Implement {auth_method} authentication",
                acceptance_criteria=[
                    "Users can sign up",
                    "Users can log in",
                    "Sessions are secure",
                    "Logout works correctly",
                ],
                priority=priority,
            )
        )
        priority += 1

    # External integrations
    external_apis = answers.get("external_apis", "")
    if external_apis and external_apis != "None":
        stories.append(
            UserStory(
                id=priority,
                title="External Integrations",
                description=f"Integrate with: {external_apis}",
                acceptance_criteria=[
                    "API connections established",
                    "Error handling for API failures",
                    "Proper authentication with external services",
                ],
                priority=priority,
            )
        )
        priority += 1

    # Core feature based on MVP scope
    mvp_scope = answers.get("mvp_scope", "Basic CRUD")
    stories.append(
        UserStory(
            id=priority,
            title="Core Feature Implementation",
            description=f"Implement core {session.topic} functionality ({mvp_scope})",
            acceptance_criteria=[
                "Core feature works as expected",
                "Basic user flow complete",
                "No critical bugs",
            ],
            priority=priority,
        )
    )
    priority += 1

    # Error handling
    error_handling = answers.get("error_handling", "")
    if error_handling and "All" in error_handling:
        stories.append(
            UserStory(
                id=priority,
                title="Error Handling",
                description="Implement comprehensive error handling",
                acceptance_criteria=[
                    "User-friendly error messages",
                    "Errors are logged",
                    "No unhandled exceptions",
                ],
                priority=priority,
            )
        )
        priority += 1

    # Testing based on requirements
    testing_level = answers.get("testing_level", "Minimal")
    if testing_level != "Minimal":
        stories.append(
            UserStory(
                id=priority,
                title="Testing Implementation",
                description=f"Add {testing_level}",
                acceptance_criteria=[
                    "Tests for core functionality",
                    "All tests passing",
                    "Test coverage meets requirements",
                ],
                priority=priority,
            )
        )
        priority += 1

    # Documentation
    stories.append(
        UserStory(
            id=priority,
            title="Documentation",
            description="Create basic documentation",
            acceptance_criteria=[
                "README with setup instructions",
                "API documentation if applicable",
                "Code is well-commented",
            ],
            priority=priority,
        )
    )

    # Build PRD
    description_parts = [f"Project: {session.topic}"]

    # Add context from answers
    primary_user = answers.get("primary_user", "")
    if primary_user:
        description_parts.append(f"Target users: {primary_user}")

    mvp_scope = answers.get("mvp_scope", "")
    if mvp_scope:
        description_parts.append(f"Scope: {mvp_scope}")

    return PRD(
        project_name=session.topic,
        description="\n".join(description_parts),
        created_at=datetime.now(UTC),
        stories=stories,
    )
