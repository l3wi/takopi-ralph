"""Tests for state management."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from takopi_ralph.state import LoopResult, LoopStatus, StateManager
from takopi_ralph.state.models import WorkType


@pytest.fixture
def tmp_state_dir(tmp_path: Path) -> Path:
    """Create a temporary state directory."""
    state_dir = tmp_path / ".ralph"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def state_manager(tmp_state_dir: Path) -> StateManager:
    """Create a StateManager with temp directory."""
    return StateManager(tmp_state_dir)


class TestStateManager:
    """Tests for StateManager class."""

    def test_exists_false_when_no_file(self, state_manager: StateManager) -> None:
        """Test exists returns False when no state file."""
        assert not state_manager.exists()

    def test_load_returns_empty_state_when_no_file(self, state_manager: StateManager) -> None:
        """Test load returns empty state when no file exists."""
        state = state_manager.load()
        assert state.current_loop == 0
        assert state.status == LoopStatus.IDLE

    def test_save_creates_file(self, state_manager: StateManager) -> None:
        """Test save creates state file."""
        state_manager.start_session("test-project")
        assert state_manager.exists()
        assert state_manager.state_file.exists()

    def test_start_session(self, state_manager: StateManager) -> None:
        """Test starting a new session."""
        state = state_manager.start_session(
            project_name="my-project",
            session_id="abc123",
            max_loops=50,
        )
        assert state.project_name == "my-project"
        assert state.session_id == "abc123"
        assert state.max_loops == 50
        assert state.status == LoopStatus.RUNNING

    def test_update_records_result(self, state_manager: StateManager) -> None:
        """Test updating state with loop result."""
        state_manager.start_session("test-project")

        result = LoopResult(
            loop_number=1,
            tasks_completed=2,
            files_modified=3,
            work_type=WorkType.IMPLEMENTATION,
        )
        state = state_manager.update(result)

        assert state.current_loop == 1
        assert len(state.recent_results) == 1
        assert state.recent_results[0].tasks_completed == 2

    def test_end_session(self, state_manager: StateManager) -> None:
        """Test ending a session."""
        state_manager.start_session("test-project")
        state = state_manager.end_session("All done", LoopStatus.COMPLETED)

        assert state.status == LoopStatus.COMPLETED
        assert state.exit_reason == "All done"

    def test_is_running(self, state_manager: StateManager) -> None:
        """Test is_running check."""
        assert not state_manager.is_running()

        state_manager.start_session("test-project")
        assert state_manager.is_running()

        state_manager.end_session("done", LoopStatus.COMPLETED)
        assert not state_manager.is_running()

    def test_reset(self, state_manager: StateManager) -> None:
        """Test reset clears all files."""
        state_manager.start_session("test-project")
        state_manager.set_session_id("abc123")

        assert state_manager.state_file.exists()
        assert state_manager.session_file.exists()

        state_manager.reset()

        assert not state_manager.state_file.exists()
        assert not state_manager.session_file.exists()

    def test_session_id_roundtrip(self, state_manager: StateManager) -> None:
        """Test session ID storage and retrieval."""
        assert state_manager.get_session_id() is None

        state_manager.set_session_id("session-xyz")
        assert state_manager.get_session_id() == "session-xyz"

    def test_load_handles_corrupted_file(self, state_manager: StateManager) -> None:
        """Test load handles corrupted JSON gracefully."""
        state_manager._ensure_dir()
        state_manager.state_file.write_text("not valid json {{{")

        # Should return empty state instead of raising
        state = state_manager.load()
        assert state.current_loop == 0

    def test_get_session_id_handles_corrupted_file(self, state_manager: StateManager) -> None:
        """Test get_session_id handles corrupted file."""
        state_manager._ensure_dir()
        state_manager.session_file.write_text("corrupted")

        assert state_manager.get_session_id() is None

    def test_atomic_write_creates_file(self, state_manager: StateManager) -> None:
        """Test atomic write creates file correctly."""
        state_manager._ensure_dir()
        test_file = state_manager.state_dir / "test.json"

        state_manager._atomic_write(test_file, '{"key": "value"}')

        assert test_file.exists()
        data = json.loads(test_file.read_text())
        assert data["key"] == "value"

    def test_get_status_summary(self, state_manager: StateManager) -> None:
        """Test status summary generation."""
        # No session
        summary = state_manager.get_status_summary()
        assert "No active" in summary

        # Active session
        state_manager.start_session("my-project")
        summary = state_manager.get_status_summary()
        assert "my-project" in summary
        assert "running" in summary
