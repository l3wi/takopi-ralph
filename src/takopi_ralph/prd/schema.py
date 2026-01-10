"""prd.json Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class UserStory(BaseModel):
    """A single user story in the PRD."""

    id: int
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    passes: bool = False
    priority: int = 1
    notes: str = ""

    def mark_complete(self) -> None:
        """Mark this story as complete."""
        self.passes = True

    def mark_incomplete(self) -> None:
        """Mark this story as incomplete."""
        self.passes = False


class PRD(BaseModel):
    """Product Requirements Document with user stories."""

    project_name: str
    description: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    branch_name: str | None = None
    stories: list[UserStory] = Field(default_factory=list)

    def next_story(self) -> UserStory | None:
        """Return highest priority story where passes=False."""
        pending = [s for s in self.stories if not s.passes]
        if not pending:
            return None
        return min(pending, key=lambda s: (s.priority, s.id))

    def all_complete(self) -> bool:
        """Check if all stories are complete."""
        return all(s.passes for s in self.stories)

    def pending_count(self) -> int:
        """Count of stories not yet complete."""
        return sum(1 for s in self.stories if not s.passes)

    def completed_count(self) -> int:
        """Count of completed stories."""
        return sum(1 for s in self.stories if s.passes)

    def total_count(self) -> int:
        """Total number of stories."""
        return len(self.stories)

    def add_story(
        self,
        title: str,
        description: str,
        acceptance_criteria: list[str] | None = None,
        priority: int | None = None,
    ) -> UserStory:
        """Add a new story to the PRD."""
        story_id = max((s.id for s in self.stories), default=0) + 1
        story_priority = priority if priority is not None else story_id

        story = UserStory(
            id=story_id,
            title=title,
            description=description,
            acceptance_criteria=acceptance_criteria or [],
            priority=story_priority,
        )
        self.stories.append(story)
        return story

    def get_story(self, story_id: int) -> UserStory | None:
        """Get a story by ID."""
        for story in self.stories:
            if story.id == story_id:
                return story
        return None

    def mark_story_complete(self, story_id: int) -> bool:
        """Mark a story as complete by ID. Returns True if found."""
        story = self.get_story(story_id)
        if story:
            story.mark_complete()
            return True
        return False

    def progress_summary(self) -> str:
        """Return a human-readable progress summary."""
        completed = self.completed_count()
        total = self.total_count()
        if total == 0:
            return "No stories defined"
        pct = int(completed / total * 100)
        return f"{completed}/{total} stories complete ({pct}%)"
