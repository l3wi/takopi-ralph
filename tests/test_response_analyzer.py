"""Tests for response analyzer."""

from __future__ import annotations

from takopi_ralph.analysis import ResponseAnalyzer, parse_ralph_status
from takopi_ralph.state.models import TestsStatus, WorkType


class TestStatusParser:
    """Tests for RALPH_STATUS block parsing."""

    def test_parse_valid_block(self, sample_ralph_response):
        """Should parse a valid RALPH_STATUS block."""
        status = parse_ralph_status(sample_ralph_response)

        assert status is not None
        assert status.status == "IN_PROGRESS"
        assert status.tasks_completed == 1
        assert status.files_modified == 2
        assert status.tests_status == TestsStatus.PASSING
        assert status.work_type == WorkType.IMPLEMENTATION
        assert status.exit_signal is False
        assert "Continue" in status.recommendation

    def test_parse_complete_block(self, sample_complete_response):
        """Should parse a COMPLETE status block."""
        status = parse_ralph_status(sample_complete_response)

        assert status is not None
        assert status.status == "COMPLETE"
        assert status.exit_signal is True

    def test_parse_missing_block(self):
        """Should return None when no status block."""
        text = "Just some text without a status block"
        status = parse_ralph_status(text)

        assert status is None

    def test_parse_partial_block(self):
        """Should handle partial/malformed blocks."""
        text = """
---RALPH_STATUS---
STATUS: IN_PROGRESS
---END_RALPH_STATUS---
"""
        status = parse_ralph_status(text)

        assert status is not None
        assert status.status == "IN_PROGRESS"
        assert status.tasks_completed == 0  # Default
        assert status.exit_signal is False  # Default


class TestResponseAnalyzer:
    """Tests for ResponseAnalyzer class."""

    def test_analyze_with_status_block(self, temp_dir, sample_ralph_response):
        """Should use structured status block when present."""
        analyzer = ResponseAnalyzer(str(temp_dir))
        result = analyzer.analyze(sample_ralph_response, loop_number=1)

        assert result.status == "IN_PROGRESS"
        assert result.tasks_completed == 1
        assert result.confidence_score >= 80  # High confidence for structured

    def test_analyze_without_status_block(self, temp_dir):
        """Should fall back to text analysis."""
        analyzer = ResponseAnalyzer(str(temp_dir))
        text = "I've implemented the feature. All done!"

        result = analyzer.analyze(text, loop_number=1)

        # Text analysis should detect completion keywords
        assert result.has_completion_signal is True
        assert "done" in result.work_summary.lower() or "Text analysis" in result.work_summary

    def test_detect_test_only_loop(self, temp_dir):
        """Should detect test-only loops."""
        analyzer = ResponseAnalyzer(str(temp_dir))
        text = """
Running npm test...
All tests passing.
No changes needed.
"""
        result = analyzer.analyze(text, loop_number=1)

        # Should detect test patterns but no implementation
        assert result.work_type in [WorkType.TESTING, WorkType.UNKNOWN]

    def test_detect_errors(self, temp_dir):
        """Should count error messages."""
        analyzer = ResponseAnalyzer(str(temp_dir))
        text = """
Error: Something went wrong
ERROR: Another error
Exception occurred
"""
        result = analyzer.analyze(text, loop_number=1)

        assert result.error_count >= 2  # At least some errors detected

    def test_filter_json_error_fields(self, temp_dir):
        """Should not count JSON field names as errors."""
        analyzer = ResponseAnalyzer(str(temp_dir))
        text = """
{
    "has_error": false,
    "is_error": false,
    "error_count": 0
}
Success!
"""
        result = analyzer.analyze(text, loop_number=1)

        # JSON fields should be filtered out
        assert result.error_count == 0

    def test_to_loop_result(self, temp_dir, sample_ralph_response):
        """Should convert analysis to LoopResult."""
        analyzer = ResponseAnalyzer(str(temp_dir))
        result = analyzer.analyze(sample_ralph_response, loop_number=5)

        loop_result = result.to_loop_result()

        assert loop_result.loop_number == 5
        assert loop_result.status == "IN_PROGRESS"
        assert loop_result.work_type == WorkType.IMPLEMENTATION
