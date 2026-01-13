"""PRD file management."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from pydantic import ValidationError

from .schema import PRD, UserStory

logger = logging.getLogger(__name__)


class PRDValidationError(Exception):
    """Raised when PRD validation fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        super().__init__(message)
        self.errors = errors or []


class PRDManager:
    """Manages prd.json file operations."""

    def __init__(self, prd_path: Path | str = "prd.json"):
        self.prd_path = Path(prd_path)

    def exists(self) -> bool:
        """Check if prd.json exists."""
        return self.prd_path.exists()

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the PRD file against the schema.

        Returns:
            (is_valid, errors) tuple. errors is empty if valid.
        """
        if not self.exists():
            return False, ["prd.json does not exist"]

        try:
            content = self.prd_path.read_text()
            data = json.loads(content)
        except json.JSONDecodeError as e:
            return False, [f"Invalid JSON: {e}"]
        except OSError as e:
            return False, [f"Cannot read file: {e}"]

        # Check for common wrong schema patterns
        errors = []

        # Check for wrong field names
        if "name" in data and "project_name" not in data:
            errors.append("Found 'name' but expected 'project_name'")
        if "tasks" in data and "stories" not in data:
            errors.append("Found 'tasks' but expected 'stories'")

        # Try Pydantic validation
        try:
            PRD.model_validate(data)
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"])
                errors.append(f"{loc}: {err['msg']}")

        return len(errors) == 0, errors

    def load(self) -> PRD:
        """Load PRD from file. Creates empty PRD if file doesn't exist or corrupted.

        Note: This method logs warnings on failures but doesn't raise exceptions.
        Use load_strict() for user-facing commands where errors should be visible.
        """
        if not self.exists():
            logger.debug("PRD file does not exist: %s", self.prd_path)
            return PRD(project_name="", description="")

        try:
            content = self.prd_path.read_text()
            data = json.loads(content)
            return PRD.model_validate(data)
        except json.JSONDecodeError as e:
            logger.warning("PRD file has invalid JSON: %s - %s", self.prd_path, e)
            return PRD(project_name="", description="")
        except ValidationError as e:
            logger.warning(
                "PRD file failed schema validation: %s - %d errors",
                self.prd_path,
                len(e.errors()),
            )
            return PRD(project_name="", description="")
        except OSError as e:
            logger.warning("Cannot read PRD file: %s - %s", self.prd_path, e)
            return PRD(project_name="", description="")

    def load_strict(self) -> PRD:
        """Load PRD from file with strict validation. Raises on errors."""
        if not self.exists():
            raise PRDValidationError("prd.json does not exist")

        is_valid, errors = self.validate()
        if not is_valid:
            raise PRDValidationError(
                f"PRD validation failed with {len(errors)} error(s)", errors
            )

        return self.load()

    def save(self, prd: PRD) -> None:
        """Save PRD to file atomically."""
        content = prd.model_dump_json(indent=2)
        self._atomic_write(self.prd_path, content)

    def _atomic_write(self, path: Path, content: str) -> None:
        """Write content to file atomically using temp file + rename."""
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with open(fd, "w") as f:
                f.write(content)
            Path(tmp_path).replace(path)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

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
        logger.info("mark_complete called for story_id=%d, prd_path=%s", story_id, self.prd_path)
        prd = self.load()
        if prd.mark_story_complete(story_id):
            logger.info("Story %d marked complete, saving to %s", story_id, self.prd_path)
            self.save(prd)
            return True
        logger.warning("Story %d not found or already complete", story_id)
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
