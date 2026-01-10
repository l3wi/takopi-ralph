"""Tests for clarify flow."""

from __future__ import annotations

from takopi_ralph.clarify import ClarifyFlow, ClarifySession, build_prd_from_session
from takopi_ralph.clarify.questions import get_all_questions


class TestClarifySession:
    """Tests for ClarifySession class."""

    def test_create_session(self):
        """Should create a session with topic."""
        session = ClarifySession(topic="My Project")

        assert session.topic == "My Project"
        assert session.current_question_index == 0
        assert session.is_complete is False

    def test_current_question(self):
        """Should return current question."""
        session = ClarifySession(topic="Test")
        question = session.current_question()

        assert question is not None
        assert question.question  # Has question text

    def test_record_answer(self):
        """Should record answer and advance."""
        session = ClarifySession(topic="Test")
        question = session.current_question()

        has_more = session.record_answer("Test Answer")

        assert has_more is True  # More questions remain
        assert question.id in session.answers
        assert session.answers[question.id] == "Test Answer"
        assert session.current_question_index == 1

    def test_skip_question(self):
        """Should skip question and advance."""
        session = ClarifySession(topic="Test")

        has_more = session.skip_question()

        assert has_more is True
        assert session.current_question_index == 1
        assert len(session.answers) == 0

    def test_complete_all_questions(self):
        """Should mark complete after all questions."""
        session = ClarifySession(topic="Test")
        questions = get_all_questions()

        # Answer all questions
        for _ in questions:
            session.skip_question()

        assert session.is_complete is True
        assert session.current_question() is None

    def test_progress_text(self):
        """Should return progress indicator."""
        session = ClarifySession(topic="Test")
        progress = session.progress_text()

        assert "/" in progress  # "1/10" format
        assert "1" in progress


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

    def test_update_session(self, temp_dir):
        """Should persist session updates."""
        flow = ClarifyFlow(temp_dir)

        session = flow.create_session("Test")
        session.record_answer("Answer 1")
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


class TestPRDBuilder:
    """Tests for building PRD from clarify session."""

    def test_build_basic_prd(self):
        """Should build PRD with basic stories."""
        session = ClarifySession(topic="Test App")
        prd = build_prd_from_session(session)

        assert prd.project_name == "Test App"
        assert len(prd.stories) > 0
        assert prd.stories[0].title == "Project Setup"

    def test_build_prd_with_answers(self):
        """Should build PRD incorporating answers."""
        session = ClarifySession(topic="Test App")
        session.answers = {
            "mvp_scope": "Full feature set",
            "auth_method": "JWT tokens",
            "testing_level": "Unit tests",
        }

        prd = build_prd_from_session(session)

        # Should have auth story
        titles = [s.title for s in prd.stories]
        assert "User Authentication" in titles

        # Should have testing story
        assert "Testing Implementation" in titles

    def test_stories_have_acceptance_criteria(self):
        """Stories should have acceptance criteria."""
        session = ClarifySession(topic="Test")
        prd = build_prd_from_session(session)

        for story in prd.stories:
            assert len(story.acceptance_criteria) > 0
