"""State models for Ralph loops."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class LoopStatus(str, Enum):
    """Status of the Ralph loop."""

    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    HALTED = "halted"  # Circuit breaker opened


class WorkType(str, Enum):
    """Type of work performed in a loop iteration."""

    IMPLEMENTATION = "IMPLEMENTATION"
    TESTING = "TESTING"
    DOCUMENTATION = "DOCUMENTATION"
    REFACTORING = "REFACTORING"
    DEBUGGING = "DEBUGGING"
    UNKNOWN = "UNKNOWN"


class TestsStatus(str, Enum):
    """Status of tests in a loop iteration."""

    PASSING = "PASSING"
    FAILING = "FAILING"
    NOT_RUN = "NOT_RUN"


class LoopResult(BaseModel):
    """Result of a single loop iteration."""

    loop_number: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # From RALPH_STATUS block
    status: str = "IN_PROGRESS"
    tasks_completed: int = 0
    files_modified: int = 0
    tests_status: TestsStatus = TestsStatus.NOT_RUN
    work_type: WorkType = WorkType.UNKNOWN
    exit_signal: bool = False
    recommendation: str = ""

    # Analysis results
    has_completion_signal: bool = False
    is_test_only: bool = False
    is_stuck: bool = False
    has_progress: bool = False
    confidence_score: int = 0
    work_summary: str = ""
    error_count: int = 0
    current_story_complete: bool = False  # Whether Claude marked the current story as done


class RalphState(BaseModel):
    """Overall state of a Ralph loop session."""

    # Session info
    project_name: str = ""
    session_id: str | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Loop tracking
    status: LoopStatus = LoopStatus.IDLE
    current_loop: int = 0
    max_loops: int = 100

    # Exit tracking
    consecutive_test_only: int = 0
    consecutive_done_signals: int = 0
    consecutive_no_progress: int = 0
    last_progress_loop: int = 0

    # Results history (last N)
    recent_results: list[LoopResult] = Field(default_factory=list)
    max_history: int = 10

    # Exit reason if stopped
    exit_reason: str = ""

    def record_result(self, result: LoopResult) -> None:
        """Record a loop iteration result."""
        self.current_loop = result.loop_number
        self.updated_at = datetime.now(UTC)

        # Track consecutive patterns
        if result.is_test_only:
            self.consecutive_test_only += 1
        else:
            self.consecutive_test_only = 0

        if result.has_completion_signal or result.exit_signal:
            self.consecutive_done_signals += 1
        else:
            self.consecutive_done_signals = 0

        if result.has_progress or result.files_modified > 0:
            self.consecutive_no_progress = 0
            self.last_progress_loop = result.loop_number
        else:
            self.consecutive_no_progress += 1

        # Maintain rolling history
        self.recent_results.append(result)
        if len(self.recent_results) > self.max_history:
            self.recent_results = self.recent_results[-self.max_history :]

    def should_exit(
        self,
        max_test_only: int = 3,
        max_done_signals: int = 2,
    ) -> tuple[bool, str]:
        """Check if loop should exit based on patterns."""
        if self.consecutive_test_only >= max_test_only:
            return True, f"Test saturation: {max_test_only} consecutive test-only loops"

        if self.consecutive_done_signals >= max_done_signals:
            return True, f"Completion signals: {max_done_signals} consecutive done signals"

        if self.current_loop >= self.max_loops:
            return True, f"Max loops reached: {self.max_loops}"

        # Check for explicit exit signal in last result
        if self.recent_results:
            last = self.recent_results[-1]
            if last.exit_signal:
                return True, "Exit signal received from Claude"

        return False, ""

    def mark_completed(self, reason: str) -> None:
        """Mark the session as completed."""
        self.status = LoopStatus.COMPLETED
        self.exit_reason = reason
        self.updated_at = datetime.now(UTC)

    def mark_halted(self, reason: str) -> None:
        """Mark the session as halted (circuit breaker)."""
        self.status = LoopStatus.HALTED
        self.exit_reason = reason
        self.updated_at = datetime.now(UTC)

    def mark_failed(self, reason: str) -> None:
        """Mark the session as failed."""
        self.status = LoopStatus.FAILED
        self.exit_reason = reason
        self.updated_at = datetime.now(UTC)
