"""Clarify flow state machine for interactive requirements gathering."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .questions import ClarifyQuestion, get_all_questions


@dataclass
class ClarifySession:
    """State of an active clarify session."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Question tracking
    current_question_index: int = 0
    answers: dict[str, str] = field(default_factory=dict)

    # Custom questions (if None, use all default questions)
    custom_question_ids: list[str] | None = None

    # Mode: "create" for new PRD, "enhance" for improving existing
    mode: str = "create"

    # Derived requirements
    emerging_requirements: list[str] = field(default_factory=list)

    # Status
    is_complete: bool = False

    def _get_questions(self) -> list[ClarifyQuestion]:
        """Get the questions for this session."""
        all_questions = get_all_questions()
        if self.custom_question_ids is None:
            return all_questions
        # Filter to custom questions, preserving order
        return [q for q in all_questions if q.id in self.custom_question_ids]

    def current_question(self) -> ClarifyQuestion | None:
        """Get the current question."""
        questions = self._get_questions()
        if self.current_question_index >= len(questions):
            return None
        return questions[self.current_question_index]

    def record_answer(self, answer: str) -> bool:
        """Record an answer and advance to next question.

        Returns True if there are more questions.
        """
        question = self.current_question()
        if question:
            self.answers[question.id] = answer

        self.current_question_index += 1

        questions = self._get_questions()
        if self.current_question_index >= len(questions):
            self.is_complete = True
            return False

        return True

    def skip_question(self) -> bool:
        """Skip current question and advance.

        Returns True if there are more questions.
        """
        self.current_question_index += 1

        questions = self._get_questions()
        if self.current_question_index >= len(questions):
            self.is_complete = True
            return False

        return True

    def progress_text(self) -> str:
        """Get progress indicator text."""
        questions = self._get_questions()
        total = len(questions)
        current = min(self.current_question_index + 1, total)
        return f"{current}/{total}"


class ClarifyFlow:
    """Manages clarify sessions and persistence."""

    def __init__(self, state_dir: Path | str = ".ralph"):
        self.state_dir = Path(state_dir)
        self.sessions_file = self.state_dir / "clarify_sessions.json"

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

    def create_session(
        self,
        topic: str,
        questions: list[ClarifyQuestion] | None = None,
        mode: str = "create",
    ) -> ClarifySession:
        """Create a new clarify session.

        Args:
            topic: Project topic/name
            questions: Optional custom question list. If None, uses all questions.
            mode: "create" for new PRD, "enhance" for improving existing

        Returns:
            New ClarifySession
        """
        # Extract question IDs if custom questions provided
        custom_ids = [q.id for q in questions] if questions else None

        session = ClarifySession(
            topic=topic,
            custom_question_ids=custom_ids,
            mode=mode,
        )

        # Persist
        sessions = self._load_sessions()
        sessions[session.id] = {
            "id": session.id,
            "topic": session.topic,
            "created_at": session.created_at.isoformat(),
            "current_question_index": session.current_question_index,
            "answers": session.answers,
            "custom_question_ids": session.custom_question_ids,
            "mode": session.mode,
            "is_complete": session.is_complete,
        }
        self._save_sessions(sessions)

        return session

    def get_session(self, session_id: str) -> ClarifySession | None:
        """Get a session by ID."""
        sessions = self._load_sessions()
        data = sessions.get(session_id)
        if not data:
            return None

        return ClarifySession(
            id=data["id"],
            topic=data["topic"],
            created_at=datetime.fromisoformat(data["created_at"]),
            current_question_index=data["current_question_index"],
            answers=data["answers"],
            custom_question_ids=data.get("custom_question_ids"),
            mode=data.get("mode", "create"),
            is_complete=data["is_complete"],
        )

    def update_session(self, session: ClarifySession) -> None:
        """Update a session in storage."""
        sessions = self._load_sessions()
        sessions[session.id] = {
            "id": session.id,
            "topic": session.topic,
            "created_at": session.created_at.isoformat(),
            "current_question_index": session.current_question_index,
            "answers": session.answers,
            "custom_question_ids": session.custom_question_ids,
            "mode": session.mode,
            "is_complete": session.is_complete,
        }
        self._save_sessions(sessions)

    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        sessions = self._load_sessions()
        if session_id in sessions:
            del sessions[session_id]
            self._save_sessions(sessions)
