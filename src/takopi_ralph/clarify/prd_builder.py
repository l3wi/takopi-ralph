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


def enhance_prd_from_session(existing_prd: PRD, session: ClarifySession) -> PRD:
    """Enhance an existing PRD with stories based on clarify session answers.

    This function adds new stories based on answers, avoiding duplicates
    with existing stories.
    """
    answers = session.answers
    existing_titles = {s.title.lower() for s in existing_prd.stories}

    # Get next ID and priority
    next_id = max((s.id for s in existing_prd.stories), default=0) + 1
    next_priority = max((s.priority for s in existing_prd.stories), default=0) + 1

    new_stories: list[UserStory] = []

    def add_story(title: str, description: str, criteria: list[str]) -> None:
        nonlocal next_id, next_priority
        if title.lower() not in existing_titles:
            new_stories.append(
                UserStory(
                    id=next_id,
                    title=title,
                    description=description,
                    acceptance_criteria=criteria,
                    priority=next_priority,
                )
            )
            next_id += 1
            next_priority += 1

    # Authentication if needed
    auth_method = answers.get("auth_method", "")
    if auth_method and auth_method != "None needed":
        add_story(
            "User Authentication",
            f"Implement {auth_method} authentication",
            [
                "Users can sign up",
                "Users can log in",
                "Sessions are secure",
                "Logout works correctly",
            ],
        )

    # Testing based on requirements
    testing_level = answers.get("testing_level", "")
    if testing_level and testing_level != "Minimal":
        add_story(
            "Testing Implementation",
            f"Add {testing_level}",
            [
                "Tests for core functionality",
                "All tests passing",
                "Test coverage meets requirements",
            ],
        )

    # Error handling
    error_handling = answers.get("error_handling", "")
    if error_handling and ("All" in error_handling or "Comprehensive" in error_handling):
        add_story(
            "Error Handling",
            "Implement comprehensive error handling",
            [
                "User-friendly error messages",
                "Errors are logged",
                "No unhandled exceptions",
            ],
        )

    # External integrations
    external_apis = answers.get("external_apis", "")
    if external_apis and external_apis not in ("None", ""):
        add_story(
            "External Integrations",
            f"Integrate with: {external_apis}",
            [
                "API connections established",
                "Error handling for API failures",
                "Proper authentication with external services",
            ],
        )

    # MVP scope additions
    mvp_scope = answers.get("mvp_scope", "")
    if mvp_scope and mvp_scope == "Full feature set":
        add_story(
            "Extended Features",
            f"Implement additional features for {existing_prd.project_name}",
            [
                "Extended feature set complete",
                "All user flows working",
                "Performance optimized",
            ],
        )

    # Add new stories to the PRD
    existing_prd.stories.extend(new_stories)

    return existing_prd
