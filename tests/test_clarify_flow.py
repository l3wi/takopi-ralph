"""Tests for clarify flow."""

from __future__ import annotations

from takopi_ralph.clarify import ClarifyFlow, ClarifySession

# Sample questions for testing (simulating LLM-generated questions)
SAMPLE_QUESTIONS = [
    {
        "question": "What is the primary goal?",
        "options": ["MVP", "Production", "Prototype"],
        "context": "Understanding scope",
    },
    {
        "question": "What auth method?",
        "options": ["JWT", "OAuth", "Session"],
        "context": "Security requirements",
    },
    {
        "question": "What testing level?",
        "options": ["Unit", "Integration", "E2E"],
        "context": "Quality requirements",
    },
]


class TestClarifySession:
    """Tests for ClarifySession class."""

    def test_create_session(self):
        """Should create a session with topic."""
        session = ClarifySession(topic="My Project")

        assert session.topic == "My Project"
        assert session.current_question_index == 0
        assert session.is_complete is False

    def test_create_session_with_questions(self):
        """Should create a session with pending questions."""
        session = ClarifySession(
            topic="My Project",
            pending_questions=SAMPLE_QUESTIONS,
        )

        assert session.topic == "My Project"
        assert len(session.pending_questions) == 3
        assert session.has_questions() is True

    def test_current_question(self):
        """Should return current question."""
        session = ClarifySession(
            topic="Test",
            pending_questions=SAMPLE_QUESTIONS,
        )
        question = session.current_question()

        assert question is not None
        assert question["question"] == "What is the primary goal?"

    def test_current_question_empty(self):
        """Should return None when no questions."""
        session = ClarifySession(topic="Test")
        question = session.current_question()

        assert question is None

    def test_record_answer(self):
        """Should record answer and advance."""
        session = ClarifySession(
            topic="Test",
            pending_questions=SAMPLE_QUESTIONS,
        )

        has_more = session.record_answer("MVP")

        assert has_more is True  # More questions remain
        assert "What is the primary goal?" in session.answers
        assert session.answers["What is the primary goal?"] == "MVP"
        assert session.current_question_index == 1

    def test_skip_question(self):
        """Should skip question and advance."""
        session = ClarifySession(
            topic="Test",
            pending_questions=SAMPLE_QUESTIONS,
        )

        has_more = session.skip_question()

        assert has_more is True
        assert session.current_question_index == 1
        assert len(session.answers) == 0

    def test_complete_all_questions(self):
        """Should mark complete after all questions."""
        session = ClarifySession(
            topic="Test",
            pending_questions=SAMPLE_QUESTIONS,
        )

        # Answer all questions
        for _ in SAMPLE_QUESTIONS:
            session.skip_question()

        assert session.is_complete is True
        assert session.current_question() is None

    def test_progress_text(self):
        """Should return progress indicator."""
        session = ClarifySession(
            topic="Test",
            pending_questions=SAMPLE_QUESTIONS,
        )
        progress = session.progress_text()

        assert progress == "1/3"

    def test_progress_text_empty(self):
        """Should handle empty questions."""
        session = ClarifySession(topic="Test")
        progress = session.progress_text()

        assert progress == "0/0"

    def test_has_questions(self):
        """Should check if questions exist."""
        empty_session = ClarifySession(topic="Test")
        assert empty_session.has_questions() is False

        session_with_questions = ClarifySession(
            topic="Test",
            pending_questions=SAMPLE_QUESTIONS,
        )
        assert session_with_questions.has_questions() is True


class TestClarifyFlow:
    """Tests for ClarifyFlow persistence."""

    def test_create_and_get_session(self, temp_dir):
        """Should create and retrieve session."""
        flow = ClarifyFlow(temp_dir)

        session = flow.create_session("Test Project")
        retrieved = flow.get_session(session.id)

        assert retrieved is not None
        assert retrieved.id == session.id
        assert retrieved.topic == "Test Project"

    def test_create_session_with_questions(self, temp_dir):
        """Should create session with pending questions."""
        flow = ClarifyFlow(temp_dir)

        session = flow.create_session(
            topic="Test",
            pending_questions=SAMPLE_QUESTIONS,
        )
        retrieved = flow.get_session(session.id)

        assert retrieved is not None
        assert len(retrieved.pending_questions) == 3

    def test_update_session(self, temp_dir):
        """Should persist session updates."""
        flow = ClarifyFlow(temp_dir)

        session = flow.create_session(
            topic="Test",
            pending_questions=SAMPLE_QUESTIONS,
        )
        session.record_answer("MVP")
        flow.update_session(session)

        retrieved = flow.get_session(session.id)
        assert len(retrieved.answers) == 1
        assert retrieved.current_question_index == 1

    def test_delete_session(self, temp_dir):
        """Should delete session."""
        flow = ClarifyFlow(temp_dir)

        session = flow.create_session("Test")
        flow.delete_session(session.id)

        assert flow.get_session(session.id) is None

    def test_create_enhance_session(self, temp_dir):
        """Should create enhance mode session."""
        flow = ClarifyFlow(temp_dir)

        session = flow.create_session(
            topic="Test",
            mode="enhance",
            focus="testing",
        )

        assert session.mode == "enhance"
        assert session.focus == "testing"
