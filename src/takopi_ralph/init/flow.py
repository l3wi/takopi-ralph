"""Init flow state machine for interactive project setup."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path


class InitPhase(str, Enum):
    """Phase of the init flow."""

    TOPIC_INPUT = "topic_input"  # Waiting for project topic
    CHECKING = "checking"  # Running environment checks
    CLARIFYING = "clarifying"  # Transitioned to clarify flow
    COMPLETED = "completed"  # Init done


@dataclass
class InitSession:
    """State of an active init session."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Init state
    phase: InitPhase = InitPhase.TOPIC_INPUT
    topic: str = ""

    # Environment checks
    git_checked: bool = False
    git_available: bool = False
    ralph_dir_exists: bool = False

    # Transition to clarify
    clarify_session_id: str | None = None


class InitFlow:
    """Manages init sessions and persistence."""

    def __init__(self, state_dir: Path | str = ".ralph"):
        self.state_dir = Path(state_dir)
        self.sessions_file = self.state_dir / "init_sessions.json"

    def _ensure_dir(self) -> None:
        """Ensure state directory exists."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _load_sessions(self) -> dict[str, dict]:
        """Load all sessions from file."""
        if not self.sessions_file.exists():
            return {}

        try:
            content = self.sessions_file.read_text()
            return json.loads(content)
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_sessions(self, sessions: dict[str, dict]) -> None:
        """Save all sessions to file."""
        self._ensure_dir()
        content = json.dumps(sessions, indent=2, default=str)
        self.sessions_file.write_text(content)

    def create_session(self) -> InitSession:
        """Create a new init session."""
        session = InitSession()

        # Persist
        sessions = self._load_sessions()
        sessions[session.id] = self._session_to_dict(session)
        self._save_sessions(sessions)

        return session

    def _session_to_dict(self, session: InitSession) -> dict:
        """Convert session to dict for storage."""
        return {
            "id": session.id,
            "created_at": session.created_at.isoformat(),
            "phase": session.phase.value,
            "topic": session.topic,
            "git_checked": session.git_checked,
            "git_available": session.git_available,
            "ralph_dir_exists": session.ralph_dir_exists,
            "clarify_session_id": session.clarify_session_id,
        }

    def _dict_to_session(self, data: dict) -> InitSession:
        """Convert dict to session."""
        return InitSession(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            phase=InitPhase(data["phase"]),
            topic=data["topic"],
            git_checked=data.get("git_checked", False),
            git_available=data.get("git_available", False),
            ralph_dir_exists=data.get("ralph_dir_exists", False),
            clarify_session_id=data.get("clarify_session_id"),
        )

    def get_session(self, session_id: str) -> InitSession | None:
        """Get a session by ID."""
        sessions = self._load_sessions()
        data = sessions.get(session_id)
        if not data:
            return None

        return self._dict_to_session(data)

    def get_pending_session(self) -> InitSession | None:
        """Get a session waiting for topic input.

        Returns the most recent session in TOPIC_INPUT phase.
        """
        sessions = self._load_sessions()

        pending = [
            self._dict_to_session(data)
            for data in sessions.values()
            if data.get("phase") == InitPhase.TOPIC_INPUT.value
        ]

        if not pending:
            return None

        # Return most recent
        return max(pending, key=lambda s: s.created_at)

    def update_session(self, session: InitSession) -> None:
        """Update a session in storage."""
        sessions = self._load_sessions()
        sessions[session.id] = self._session_to_dict(session)
        self._save_sessions(sessions)

    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        sessions = self._load_sessions()
        if session_id in sessions:
            del sessions[session_id]
            self._save_sessions(sessions)

    def get_session_by_clarify(self, clarify_session_id: str) -> InitSession | None:
        """Get init session by its linked clarify session ID."""
        sessions = self._load_sessions()

        for data in sessions.values():
            if data.get("clarify_session_id") == clarify_session_id:
                return self._dict_to_session(data)

        return None

    def check_environment(self, cwd: Path) -> dict:
        """Check git and .ralph directory status.

        Args:
            cwd: Current working directory to check

        Returns:
            Dict with git_available and ralph_dir_exists booleans
        """
        return {
            "git_available": (cwd / ".git").exists(),
            "ralph_dir_exists": (cwd / ".ralph").exists(),
        }
