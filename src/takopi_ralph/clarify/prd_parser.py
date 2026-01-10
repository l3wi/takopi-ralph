"""Parse user descriptions into structured PRDs.

Used by /ralph prd init to create initial PRDs from detailed descriptions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..prd import PRD, UserStory

# Known tech stacks for detection
TECH_STACKS = {
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "react": "React",
    "vue": "Vue.js",
    "angular": "Angular",
    "svelte": "Svelte",
    "express": "Express.js",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "typescript": "TypeScript",
    "python": "Python",
    "node": "Node.js",
    "golang": "Go",
    "rust": "Rust",
}

# Feature keywords that suggest specific stories
FEATURE_PATTERNS = {
    "auth": ["authentication", "login", "signup", "register", "oauth", "sso", "jwt"],
    "crud": ["create", "read", "update", "delete", "crud", "manage", "add", "edit", "remove"],
    "api": ["api", "endpoint", "rest", "graphql", "backend"],
    "database": ["database", "db", "storage", "persist", "save", "store"],
    "ui": ["interface", "ui", "frontend", "dashboard", "page", "view", "display"],
    "search": ["search", "filter", "query", "find"],
    "notification": ["notification", "alert", "email", "push"],
    "payment": ["payment", "stripe", "billing", "subscription", "checkout"],
}


@dataclass
class ParsedDescription:
    """Parsed components from user description."""

    project_name: str
    description: str
    tech_stack: list[str]
    features: list[str]
    user_types: list[str]


def parse_description(text: str) -> ParsedDescription:
    """Parse user description into structured components.

    Args:
        text: Raw user description text

    Returns:
        ParsedDescription with extracted components
    """
    lines = text.strip().split("\n")
    text_lower = text.lower()

    # Extract project name from first line or "building a/an X" pattern
    project_name = _extract_project_name(lines[0], text)

    # Detect tech stack
    tech_stack = _detect_tech_stack(text_lower)

    # Extract features from bullet points and keywords
    features = _extract_features(text, text_lower)

    # Extract user types
    user_types = _extract_user_types(text_lower)

    return ParsedDescription(
        project_name=project_name,
        description=text[:500],  # Truncate for description field
        tech_stack=tech_stack,
        features=features,
        user_types=user_types,
    )


def _extract_project_name(first_line: str, full_text: str) -> str:
    """Extract project name from text."""
    # Try "building a/an X" pattern
    match = re.search(r"building (?:a|an)\s+([^.,\n]+)", full_text.lower())
    if match:
        return match.group(1).strip().title()

    # Try "project: X" or "name: X" pattern
    match = re.search(r"(?:project|name):\s*([^.,\n]+)", full_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Use first line if short enough
    if len(first_line) < 50:
        # Clean up common prefixes
        cleaned = re.sub(r"^(?:i want to build|i'm building|building)\s+", "", first_line.lower())
        return cleaned.strip().title() or "New Project"

    return "New Project"


def _detect_tech_stack(text_lower: str) -> list[str]:
    """Detect mentioned tech stack components."""
    detected = []
    for keyword, name in TECH_STACKS.items():
        if keyword in text_lower and name not in detected:
            detected.append(name)
    return detected


def _extract_features(text: str, text_lower: str) -> list[str]:
    """Extract features from bullet points and keywords."""
    features: list[str] = []

    # Extract bullet points (lines starting with -, *, •, or numbers)
    bullet_pattern = re.compile(r"^\s*(?:[-*•]|\d+\.)\s*(.+)$", re.MULTILINE)
    for match in bullet_pattern.finditer(text):
        feature = match.group(1).strip()
        if len(feature) > 5 and feature not in features:
            features.append(feature)

    # Detect feature categories from keywords
    for category, keywords in FEATURE_PATTERNS.items():
        if (
            any(kw in text_lower for kw in keywords)
            and category not in [f.lower() for f in features]
        ):
            features.append(category.title())

    return features[:10]  # Limit to 10 features


def _extract_user_types(text_lower: str) -> list[str]:
    """Extract user types mentioned in text."""
    user_patterns = [
        r"for\s+(developers?|users?|admins?|customers?|clients?)",
        r"(developers?|users?|admins?|customers?|clients?)\s+(?:can|will|should)",
        r"target(?:ed)?\s+(?:at\s+)?(developers?|users?|admins?|customers?|clients?)",
    ]

    user_types = set()
    for pattern in user_patterns:
        for match in re.finditer(pattern, text_lower):
            user_types.add(match.group(1).title())

    return list(user_types)


def parse_description_to_prd(description: str) -> PRD:
    """Parse user description into a complete PRD with stories.

    Args:
        description: User's detailed project description

    Returns:
        PRD with generated user stories
    """
    parsed = parse_description(description)

    # Create base PRD
    prd = PRD(
        project_name=parsed.project_name,
        description=parsed.description,
        stories=[],
    )

    story_id = 0

    # Always add project setup story
    story_id += 1
    prd.stories.append(
        UserStory(
            id=story_id,
            title="Project Setup",
            description=f"Initialize {parsed.project_name} project structure"
            + (f" with {', '.join(parsed.tech_stack)}" if parsed.tech_stack else ""),
            acceptance_criteria=[
                "Project scaffolded with chosen framework",
                "Dependencies installed",
                "Development environment working",
            ],
            priority=1,
        )
    )

    # Add stories for each detected feature
    for i, feature in enumerate(parsed.features):
        story_id += 1
        prd.stories.append(
            UserStory(
                id=story_id,
                title=f"Implement {feature}",
                description=f"Implement {feature.lower()} functionality for {parsed.project_name}",
                acceptance_criteria=[
                    f"{feature} feature is functional",
                    "Code follows project conventions",
                ],
                priority=i + 2,
            )
        )

    # Add testing story
    story_id += 1
    prd.stories.append(
        UserStory(
            id=story_id,
            title="Testing Implementation",
            description=f"Add tests for {parsed.project_name} core functionality",
            acceptance_criteria=[
                "Unit tests for core modules",
                "Tests pass in CI",
            ],
            priority=story_id,
        )
    )

    # Add documentation story
    story_id += 1
    prd.stories.append(
        UserStory(
            id=story_id,
            title="Documentation",
            description=f"Document {parsed.project_name} setup and usage",
            acceptance_criteria=[
                "README with setup instructions",
                "API documentation (if applicable)",
            ],
            priority=story_id,
        )
    )

    return prd
