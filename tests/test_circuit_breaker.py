"""Tests for circuit breaker."""

from __future__ import annotations

from takopi_ralph.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state_closed(self, temp_dir):
        """Circuit breaker should start in CLOSED state."""
        cb = CircuitBreaker(temp_dir)
        assert cb.get_state() == CircuitState.CLOSED

    def test_can_execute_when_closed(self, temp_dir):
        """Should allow execution when CLOSED."""
        cb = CircuitBreaker(temp_dir)
        assert cb.can_execute() is True

    def test_stays_closed_with_progress(self, temp_dir):
        """Should stay CLOSED when making progress."""
        cb = CircuitBreaker(temp_dir)

        for i in range(5):
            result = cb.record_loop_result(
                loop_number=i,
                files_changed=1,  # Progress
                has_errors=False,
            )
            assert result is True  # Can continue
            assert cb.get_state() == CircuitState.CLOSED

    def test_transitions_to_half_open(self, temp_dir):
        """Should transition to HALF_OPEN after 2 loops without progress."""
        cb = CircuitBreaker(temp_dir)

        # Two loops without progress
        cb.record_loop_result(loop_number=1, files_changed=0, has_errors=False)
        cb.record_loop_result(loop_number=2, files_changed=0, has_errors=False)

        assert cb.get_state() == CircuitState.HALF_OPEN

    def test_transitions_to_open(self, temp_dir):
        """Should transition to OPEN after threshold without progress."""
        cb = CircuitBreaker(temp_dir, no_progress_threshold=3)

        # Three loops without progress
        for i in range(3):
            cb.record_loop_result(loop_number=i, files_changed=0, has_errors=False)

        assert cb.get_state() == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_recovers_from_half_open(self, temp_dir):
        """Should recover from HALF_OPEN when progress detected."""
        cb = CircuitBreaker(temp_dir)

        # Enter HALF_OPEN
        cb.record_loop_result(loop_number=1, files_changed=0, has_errors=False)
        cb.record_loop_result(loop_number=2, files_changed=0, has_errors=False)
        assert cb.get_state() == CircuitState.HALF_OPEN

        # Make progress
        cb.record_loop_result(loop_number=3, files_changed=1, has_errors=False)
        assert cb.get_state() == CircuitState.CLOSED

    def test_opens_on_repeated_errors(self, temp_dir):
        """Should open after repeated errors."""
        cb = CircuitBreaker(temp_dir, same_error_threshold=3)

        # Three loops with errors (but with progress to avoid no-progress trigger)
        for i in range(3):
            cb.record_loop_result(loop_number=i, files_changed=1, has_errors=True)

        assert cb.get_state() == CircuitState.OPEN

    def test_reset(self, temp_dir):
        """Should reset to CLOSED state."""
        cb = CircuitBreaker(temp_dir, no_progress_threshold=2)

        # Open the circuit
        cb.record_loop_result(loop_number=1, files_changed=0, has_errors=False)
        cb.record_loop_result(loop_number=2, files_changed=0, has_errors=False)
        assert cb.get_state() == CircuitState.OPEN

        # Reset
        cb.reset("Manual reset")
        assert cb.get_state() == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_status_message(self, temp_dir):
        """Should return formatted status message."""
        cb = CircuitBreaker(temp_dir)
        message = cb.get_status_message()

        assert "Circuit Breaker" in message
        assert "CLOSED" in message
