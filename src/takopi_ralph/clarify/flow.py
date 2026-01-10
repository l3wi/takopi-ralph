"""Clarify flow state machine for interactive requirements gathering.

Manages sessions for LLM-powered PRD analysis and question flow.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class ClarifySession:
    """State of an active clarify session.

    Tracks the conversation state between LLM analysis calls,
    including pending questions and user answers.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Mode: "create" for new PRD, "enhance" for improving existing
    mode: str = "create"

    # Focus area for enhance mode (optional)
    focus: str | None = None

    # Pending questions from LLM analysis
    pending_questions: list[dict[str, Any]] = field(default_factory=list)

    # Current question index in pending_questions
    current_question_index: int = 0

    # User answers: {question_text: answer_text}
    answers: dict[str, str] = field(default_factory=dict)

    # Status
    is_complete: bool = False

    def current_question(self) -> dict[str, Any] | None:
        """Get the current question dict.

        Returns:
            Question dict with 'question', 'options', 'context' keys,
            or None if no more questions.
        """
        if self.current_question_index >= len(self.pending_questions):
            return None
        return self.pending_questions[self.current_question_index]

    def record_answer(self, answer: str) -> bool:
        """Record an answer and advance to next question.

        Args:
            answer: The user's selected answer

        Returns:
            True if there are more questions, False if complete.
        """
        question = self.current_question()
        if question:
            self.answers[question["question"]] = answer

        self.current_question_index += 1

        if self.current_question_index >= len(self.pending_questions):
            self.is_complete = True
            return False

        return True

    def skip_question(self) -> bool:
        """Skip current question and advance.

        Returns:
            True if there are more questions, False if complete.
        """
        self.current_question_index += 1

        if self.current_question_index >= len(self.pending_questions):
            self.is_complete = True
            return False

        return True

    def progress_text(self) -> str:
        """Get progress indicator text."""
        total = len(self.pending_questions)
        if total == 0:
            return "0/0"
        current = min(self.current_question_index + 1, total)
        return f"{current}/{total}"

    def has_questions(self) -> bool:
        """Check if there are pending questions."""
        return len(self.pending_questions) > 0


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
        mode: str = "create",
        focus: str | None = None,
        pending_questions: list[dict[str, Any]] | None = None,
    ) -> ClarifySession:
        """Create a new clarify session.

        Args:
            topic: Project topic/name
            mode: "create" for new PRD, "enhance" for improving existing
            focus: Focus area for enhance mode
            pending_questions: Questions from LLM analysis

        Returns:
            New ClarifySession
        """
        session = ClarifySession(
            topic=topic,
            mode=mode,
            focus=focus,
            pending_questions=pending_questions or [],
        )

        # Persist
        self._persist_session(session)
        return session

    def _persist_session(self, session: ClarifySession) -> None:
        """Persist a session to storage."""
        sessions = self._load_sessions()
        sessions[session.id] = {
            "id": session.id,
            "topic": session.topic,
            "created_at": session.created_at.isoformat(),
            "mode": session.mode,
            "focus": session.focus,
            "pending_questions": session.pending_questions,
            "current_question_index": session.current_question_index,
            "answers": session.answers,
            "is_complete": session.is_complete,
        }
        self._save_sessions(sessions)

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
            mode=data.get("mode", "create"),
            focus=data.get("focus"),
            pending_questions=data.get("pending_questions", []),
            current_question_index=data.get("current_question_index", 0),
            answers=data.get("answers", {}),
            is_complete=data.get("is_complete", False),
        )

    def update_session(self, session: ClarifySession) -> None:
        """Update a session in storage."""
        self._persist_session(session)

    def delete_session(self, session_id: str) -> None:
        """Delete a session."""
        sessions = self._load_sessions()
        if session_id in sessions:
            del sessions[session_id]
            self._save_sessions(sessions)
