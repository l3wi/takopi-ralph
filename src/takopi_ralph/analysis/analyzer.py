"""Response analyzer for Ralph loops.

Analyzes Claude responses to detect completion signals,
test-only loops, and progress indicators.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

from ..state.models import LoopResult, TestsStatus, WorkType
from .status_parser import RalphStatus, parse_ralph_status

# Completion keywords for fallback detection
COMPLETION_KEYWORDS = [
    "done",
    "complete",
    "finished",
    "all tasks complete",
    "project complete",
    "ready for review",
    "nothing to do",
    "no changes",
    "already implemented",
]

# Test-only patterns
TEST_PATTERNS = [
    r"npm test",
    r"bats",
    r"pytest",
    r"jest",
    r"cargo test",
    r"go test",
    r"running tests",
    r"vitest",
]

# Implementation patterns
IMPLEMENTATION_PATTERNS = [
    r"implementing",
    r"creating",
    r"writing",
    r"adding",
    r"function",
    r"class",
    r"component",
]

# Error patterns (two-stage filtering approach)
# Stage 1: Exclude JSON field names containing "error"
# Stage 2: Match actual error messages
ERROR_PATTERNS = [
    r"^Error:",
    r"^ERROR:",
    r"^error:",
    r"\]: error",
    r"Link: error",
    r"Error occurred",
    r"failed with error",
    r"[Ee]xception",
    r"Fatal",
    r"FATAL",
]


@dataclass
class AnalysisResult:
    """Result of analyzing a Claude response."""

    loop_number: int
    has_completion_signal: bool
    is_test_only: bool
    is_stuck: bool
    has_progress: bool
    files_modified: int
    confidence_score: int
    exit_signal: bool
    work_summary: str

    # From RALPH_STATUS block
    status: str
    work_type: WorkType
    tasks_completed: int
    tests_status: TestsStatus
    recommendation: str
    current_story_complete: bool  # Whether the current story is done

    # Computed
    error_count: int

    def to_loop_result(self) -> LoopResult:
        """Convert to LoopResult for state tracking."""
        return LoopResult(
            loop_number=self.loop_number,
            status=self.status,
            tasks_completed=self.tasks_completed,
            files_modified=self.files_modified,
            tests_status=self.tests_status,
            work_type=self.work_type,
            exit_signal=self.exit_signal,
            recommendation=self.recommendation,
            has_completion_signal=self.has_completion_signal,
            is_test_only=self.is_test_only,
            is_stuck=self.is_stuck,
            has_progress=self.has_progress,
            confidence_score=self.confidence_score,
            work_summary=self.work_summary,
            error_count=self.error_count,
            current_story_complete=self.current_story_complete,
        )


class ResponseAnalyzer:
    """Analyzes Claude responses for loop control signals."""

    def __init__(self, cwd: str | None = None):
        """Initialize analyzer.

        Args:
            cwd: Working directory for git operations. None uses current dir.
        """
        self.cwd = cwd

    def analyze(self, response: str, loop_number: int = 0) -> AnalysisResult:
        """Analyze a Claude response.

        Args:
            response: Claude's response text
            loop_number: Current loop iteration number

        Returns:
            AnalysisResult with all detected signals
        """
        # Try to parse structured RALPH_STATUS block first
        ralph_status = parse_ralph_status(response)

        if ralph_status:
            return self._analyze_structured(ralph_status, response, loop_number)
        else:
            return self._analyze_text(response, loop_number)

    def _analyze_structured(
        self,
        status: RalphStatus,
        response: str,
        loop_number: int,
    ) -> AnalysisResult:
        """Analyze using structured RALPH_STATUS block."""
        # Get files modified from git if not in status
        files_modified = status.files_modified
        if files_modified == 0:
            files_modified = self._git_files_changed()

        # Determine completion signal
        has_completion_signal = status.status == "COMPLETE" or status.exit_signal

        # Determine if test-only
        is_test_only = status.work_type == WorkType.TESTING and status.files_modified == 0

        # Determine progress
        has_progress = files_modified > 0 or status.tasks_completed > 0

        # Count errors in response
        error_count = self._count_errors(response)
        is_stuck = error_count > 5

        # Calculate confidence (high for structured responses)
        confidence = 80
        if status.exit_signal:
            confidence = 100
        elif has_progress:
            confidence += 10

        return AnalysisResult(
            loop_number=loop_number,
            has_completion_signal=has_completion_signal,
            is_test_only=is_test_only,
            is_stuck=is_stuck,
            has_progress=has_progress,
            files_modified=files_modified,
            confidence_score=confidence,
            exit_signal=status.exit_signal,
            work_summary=status.recommendation,
            status=status.status,
            work_type=status.work_type,
            tasks_completed=status.tasks_completed,
            tests_status=status.tests_status,
            recommendation=status.recommendation,
            current_story_complete=status.current_story_complete,
            error_count=error_count,
        )

    def _analyze_text(self, response: str, loop_number: int) -> AnalysisResult:
        """Analyze using text patterns (fallback)."""
        confidence = 0
        has_completion_signal = False
        work_summary = ""

        # Check for completion keywords
        response_lower = response.lower()
        for keyword in COMPLETION_KEYWORDS:
            if keyword in response_lower:
                has_completion_signal = True
                confidence += 10
                work_summary = f"Detected: {keyword}"
                break

        # Count test patterns
        test_count = sum(
            1 for pattern in TEST_PATTERNS if re.search(pattern, response, re.IGNORECASE)
        )

        # Count implementation patterns
        impl_count = sum(
            1 for pattern in IMPLEMENTATION_PATTERNS if re.search(pattern, response, re.IGNORECASE)
        )

        # Determine if test-only
        is_test_only = test_count > 0 and impl_count == 0

        # Get files modified from git
        files_modified = self._git_files_changed()
        has_progress = files_modified > 0

        if has_progress:
            confidence += 20

        # Count errors
        error_count = self._count_errors(response)
        is_stuck = error_count > 5

        # Determine work type
        if is_test_only:
            work_type = WorkType.TESTING
        elif impl_count > 0:
            work_type = WorkType.IMPLEMENTATION
        else:
            work_type = WorkType.UNKNOWN

        # Determine exit signal based on confidence
        exit_signal = confidence >= 40 or has_completion_signal

        return AnalysisResult(
            loop_number=loop_number,
            has_completion_signal=has_completion_signal,
            is_test_only=is_test_only,
            is_stuck=is_stuck,
            has_progress=has_progress,
            files_modified=files_modified,
            confidence_score=confidence,
            exit_signal=exit_signal,
            work_summary=work_summary or "Text analysis (no RALPH_STATUS block)",
            status="IN_PROGRESS" if not has_completion_signal else "COMPLETE",
            work_type=work_type,
            tasks_completed=0,
            tests_status=TestsStatus.NOT_RUN,
            recommendation="",
            current_story_complete=has_completion_signal,  # Infer from completion signal
            error_count=error_count,
        )

    def _git_files_changed(self) -> int:
        """Get number of files changed from git diff."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only"],
                capture_output=True,
                text=True,
                cwd=self.cwd,
                timeout=5,
            )
            if result.returncode == 0:
                files = [f for f in result.stdout.strip().split("\n") if f]
                return len(files)
        except (subprocess.SubprocessError, OSError):
            pass
        return 0

    def _count_errors(self, response: str) -> int:
        """Count error messages in response using two-stage filtering."""
        # Stage 1: Filter out JSON field patterns
        lines = response.split("\n")
        filtered_lines = [
            line for line in lines if not re.search(r'"[^"]*error[^"]*":', line, re.IGNORECASE)
        ]
        filtered_text = "\n".join(filtered_lines)

        # Stage 2: Count actual error patterns
        count = 0
        for pattern in ERROR_PATTERNS:
            count += len(re.findall(pattern, filtered_text, re.MULTILINE))

        return count
