"""Circuit breaker for Ralph loops.

Based on Michael Nygard's "Release It!" pattern.
Prevents runaway token consumption by detecting stagnation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"  # Normal operation, progress detected
    HALF_OPEN = "HALF_OPEN"  # Monitoring mode, checking for recovery
    OPEN = "OPEN"  # Failure detected, execution halted


class CircuitBreakerState(BaseModel):
    """Persisted circuit breaker state."""

    state: CircuitState = CircuitState.CLOSED
    last_change: datetime = Field(default_factory=lambda: datetime.now(UTC))
    consecutive_no_progress: int = 0
    consecutive_same_error: int = 0
    last_progress_loop: int = 0
    total_opens: int = 0
    current_loop: int = 0
    reason: str = ""


class CircuitBreakerHistory(BaseModel):
    """History of circuit breaker state transitions."""

    transitions: list[dict] = Field(default_factory=list)


class CircuitBreaker:
    """Circuit breaker to prevent runaway Ralph loops.

    State transitions:
    - CLOSED -> HALF_OPEN: After 2 loops without progress
    - HALF_OPEN -> CLOSED: If progress detected
    - HALF_OPEN -> OPEN: If no recovery after threshold
    - OPEN -> CLOSED: Manual reset only
    """

    # Configuration thresholds
    NO_PROGRESS_THRESHOLD = 3  # Open after N loops with no file changes
    SAME_ERROR_THRESHOLD = 5  # Open after N loops with same error
    HALF_OPEN_THRESHOLD = 2  # Enter HALF_OPEN after N loops without progress

    def __init__(
        self,
        state_dir: Path | str = ".ralph",
        no_progress_threshold: int | None = None,
        same_error_threshold: int | None = None,
    ):
        self.state_dir = Path(state_dir)
        self.state_file = self.state_dir / "circuit_breaker.json"
        self.history_file = self.state_dir / "circuit_breaker_history.json"

        # Allow threshold override
        if no_progress_threshold is not None:
            self.NO_PROGRESS_THRESHOLD = no_progress_threshold
        if same_error_threshold is not None:
            self.SAME_ERROR_THRESHOLD = same_error_threshold

    def _ensure_dir(self) -> None:
        """Ensure state directory exists."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> CircuitBreakerState:
        """Load state from file."""
        if not self.state_file.exists():
            return CircuitBreakerState()

        try:
            content = self.state_file.read_text()
            data = json.loads(content)
            return CircuitBreakerState.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            # Corrupted file, reset
            return CircuitBreakerState()

    def _save_state(self, state: CircuitBreakerState) -> None:
        """Save state to file."""
        self._ensure_dir()
        content = state.model_dump_json(indent=2)
        self.state_file.write_text(content)

    def _log_transition(
        self,
        from_state: CircuitState,
        to_state: CircuitState,
        reason: str,
        loop_number: int,
    ) -> None:
        """Log a state transition."""
        self._ensure_dir()

        # Load existing history
        if self.history_file.exists():
            try:
                content = self.history_file.read_text()
                history = CircuitBreakerHistory.model_validate(json.loads(content))
            except (json.JSONDecodeError, ValueError):
                history = CircuitBreakerHistory()
        else:
            history = CircuitBreakerHistory()

        # Add transition
        history.transitions.append(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "loop": loop_number,
                "from_state": from_state.value,
                "to_state": to_state.value,
                "reason": reason,
            }
        )

        # Keep only last 50 transitions
        if len(history.transitions) > 50:
            history.transitions = history.transitions[-50:]

        # Save
        self.history_file.write_text(history.model_dump_json(indent=2))

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self._load_state().state

    def can_execute(self) -> bool:
        """Check if circuit allows execution."""
        state = self.get_state()
        return state != CircuitState.OPEN

    def record_loop_result(
        self,
        loop_number: int,
        files_changed: int,
        has_errors: bool,
        output_length: int = 0,
    ) -> bool:
        """Record a loop execution result.

        Args:
            loop_number: Current loop number
            files_changed: Number of files modified (from git diff)
            has_errors: Whether errors were detected
            output_length: Length of output (for trend analysis)

        Returns:
            True if can continue, False if circuit opened
        """
        state = self._load_state()
        current_state = state.state

        # Track progress
        has_progress = files_changed > 0

        if has_progress:
            state.consecutive_no_progress = 0
            state.last_progress_loop = loop_number
        else:
            state.consecutive_no_progress += 1

        # Track errors
        if has_errors:
            state.consecutive_same_error += 1
        else:
            state.consecutive_same_error = 0

        # State transitions
        new_state = current_state
        reason = ""

        if current_state == CircuitState.CLOSED:
            # Normal operation - check for failure conditions
            if state.consecutive_no_progress >= self.NO_PROGRESS_THRESHOLD:
                new_state = CircuitState.OPEN
                reason = (
                    f"No progress detected in {state.consecutive_no_progress} consecutive loops"
                )
            elif state.consecutive_same_error >= self.SAME_ERROR_THRESHOLD:
                new_state = CircuitState.OPEN
                reason = f"Same error repeated in {state.consecutive_same_error} consecutive loops"
            elif state.consecutive_no_progress >= self.HALF_OPEN_THRESHOLD:
                new_state = CircuitState.HALF_OPEN
                reason = f"Monitoring: {state.consecutive_no_progress} loops without progress"

        elif current_state == CircuitState.HALF_OPEN:
            # Monitoring mode - either recover or fail
            if has_progress:
                new_state = CircuitState.CLOSED
                reason = "Progress detected, circuit recovered"
            elif state.consecutive_no_progress >= self.NO_PROGRESS_THRESHOLD:
                new_state = CircuitState.OPEN
                reason = f"No recovery, opening circuit after {state.consecutive_no_progress} loops"

        # OPEN state stays open (requires manual reset)

        # Update state
        state.current_loop = loop_number
        if new_state != current_state:
            state.state = new_state
            state.last_change = datetime.now(UTC)
            state.reason = reason

            if new_state == CircuitState.OPEN:
                state.total_opens += 1

            self._log_transition(current_state, new_state, reason, loop_number)

        self._save_state(state)

        return new_state != CircuitState.OPEN

    def reset(self, reason: str = "Manual reset") -> None:
        """Reset circuit breaker to CLOSED state."""
        old_state = self._load_state()
        new_state = CircuitBreakerState(reason=reason)

        self._save_state(new_state)
        self._log_transition(old_state.state, CircuitState.CLOSED, reason, old_state.current_loop)

    def get_status(self) -> dict:
        """Get detailed status for display."""
        state = self._load_state()
        return {
            "state": state.state.value,
            "reason": state.reason,
            "consecutive_no_progress": state.consecutive_no_progress,
            "consecutive_same_error": state.consecutive_same_error,
            "last_progress_loop": state.last_progress_loop,
            "current_loop": state.current_loop,
            "total_opens": state.total_opens,
        }

    def get_status_message(self) -> str:
        """Get human-readable status message."""
        state = self._load_state()

        icon = {
            CircuitState.CLOSED: "green",
            CircuitState.HALF_OPEN: "yellow",
            CircuitState.OPEN: "red",
        }[state.state]

        lines = [
            f"Circuit Breaker: {state.state.value} ({icon})",
            f"Loops since progress: {state.consecutive_no_progress}",
        ]

        if state.reason:
            lines.append(f"Reason: {state.reason}")

        if state.consecutive_same_error > 0:
            lines.append(f"Consecutive errors: {state.consecutive_same_error}")

        return "\n".join(lines)
