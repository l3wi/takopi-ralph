"""PRD file management."""

from __future__ import annotations

import json
from pathlib import Path

from .schema import PRD, UserStory


class PRDManager:
    """Manages prd.json file operations."""

    def __init__(self, prd_path: Path | str = "prd.json"):
        self.prd_path = Path(prd_path)

    def exists(self) -> bool:
        """Check if prd.json exists."""
        return self.prd_path.exists()

    def load(self) -> PRD:
        """Load PRD from file. Creates empty PRD if file doesn't exist."""
        if not self.exists():
            return PRD(project_name="", description="")

        content = self.prd_path.read_text()
        data = json.loads(content)
        return PRD.model_validate(data)

    def save(self, prd: PRD) -> None:
        """Save PRD to file."""
        content = prd.model_dump_json(indent=2)
        self.prd_path.write_text(content)

    def create(
        self,
        project_name: str,
        description: str,
        stories: list[dict] | None = None,
    ) -> PRD:
        """Create a new PRD and save it."""
        prd = PRD(
            project_name=project_name,
            description=description,
        )

        if stories:
            for story_data in stories:
                prd.add_story(
                    title=story_data.get("title", ""),
                    description=story_data.get("description", ""),
                    acceptance_criteria=story_data.get("acceptance_criteria", []),
                    priority=story_data.get("priority"),
                )

        self.save(prd)
        return prd

    def add_story(
        self,
        title: str,
        description: str,
        acceptance_criteria: list[str] | None = None,
        priority: int | None = None,
    ) -> UserStory:
        """Add a story to the PRD and save."""
        prd = self.load()
        story = prd.add_story(title, description, acceptance_criteria, priority)
        self.save(prd)
        return story

    def mark_complete(self, story_id: int) -> bool:
        """Mark a story as complete and save."""
        prd = self.load()
        if prd.mark_story_complete(story_id):
            self.save(prd)
            return True
        return False

    def next_story(self) -> UserStory | None:
        """Get the next story to work on."""
        prd = self.load()
        return prd.next_story()

    def all_complete(self) -> bool:
        """Check if all stories are complete."""
        prd = self.load()
        return prd.all_complete()

    def progress_summary(self) -> str:
        """Get progress summary."""
        prd = self.load()
        return prd.progress_summary()
