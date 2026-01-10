"""Parser for RALPH_STATUS blocks in Claude responses."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..state.models import TestsStatus, WorkType


@dataclass
class RalphStatus:
    """Parsed RALPH_STATUS block."""

    status: str  # IN_PROGRESS, COMPLETE, BLOCKED
    tasks_completed: int
    files_modified: int
    tests_status: TestsStatus
    work_type: WorkType
    exit_signal: bool
    recommendation: str

    @classmethod
    def empty(cls) -> RalphStatus:
        """Return an empty/default status."""
        return cls(
            status="UNKNOWN",
            tasks_completed=0,
            files_modified=0,
            tests_status=TestsStatus.NOT_RUN,
            work_type=WorkType.UNKNOWN,
            exit_signal=False,
            recommendation="",
        )


# Regex to find the RALPH_STATUS block
_STATUS_BLOCK_RE = re.compile(
    r"---RALPH_STATUS---\s*\n(.*?)\n---END_RALPH_STATUS---",
    re.DOTALL | re.IGNORECASE,
)

# Regex patterns for each field
_FIELD_PATTERNS = {
    "status": re.compile(r"STATUS:\s*(IN_PROGRESS|COMPLETE|BLOCKED)", re.IGNORECASE),
    "tasks_completed": re.compile(r"TASKS_COMPLETED_THIS_LOOP:\s*(\d+)", re.IGNORECASE),
    "files_modified": re.compile(r"FILES_MODIFIED:\s*(\d+)", re.IGNORECASE),
    "tests_status": re.compile(r"TESTS_STATUS:\s*(PASSING|FAILING|NOT_RUN)", re.IGNORECASE),
    "work_type": re.compile(
        r"WORK_TYPE:\s*(IMPLEMENTATION|TESTING|DOCUMENTATION|REFACTORING|DEBUGGING)",
        re.IGNORECASE,
    ),
    "exit_signal": re.compile(r"EXIT_SIGNAL:\s*(true|false)", re.IGNORECASE),
    "recommendation": re.compile(r"RECOMMENDATION:\s*(.+?)(?:\n|$)", re.IGNORECASE),
}


def parse_ralph_status(text: str) -> RalphStatus | None:
    """Parse a RALPH_STATUS block from text.

    Args:
        text: Claude response text that may contain a RALPH_STATUS block

    Returns:
        Parsed RalphStatus or None if block not found
    """
    # Find the status block
    match = _STATUS_BLOCK_RE.search(text)
    if not match:
        return None

    block_content = match.group(1)

    # Parse each field
    result = RalphStatus.empty()

    # Status
    status_match = _FIELD_PATTERNS["status"].search(block_content)
    if status_match:
        result.status = status_match.group(1).upper()

    # Tasks completed
    tasks_match = _FIELD_PATTERNS["tasks_completed"].search(block_content)
    if tasks_match:
        result.tasks_completed = int(tasks_match.group(1))

    # Files modified
    files_match = _FIELD_PATTERNS["files_modified"].search(block_content)
    if files_match:
        result.files_modified = int(files_match.group(1))

    # Tests status
    tests_match = _FIELD_PATTERNS["tests_status"].search(block_content)
    if tests_match:
        status_str = tests_match.group(1).upper()
        try:
            result.tests_status = TestsStatus(status_str)
        except ValueError:
            pass

    # Work type
    work_match = _FIELD_PATTERNS["work_type"].search(block_content)
    if work_match:
        work_str = work_match.group(1).upper()
        try:
            result.work_type = WorkType(work_str)
        except ValueError:
            pass

    # Exit signal
    exit_match = _FIELD_PATTERNS["exit_signal"].search(block_content)
    if exit_match:
        result.exit_signal = exit_match.group(1).lower() == "true"

    # Recommendation
    rec_match = _FIELD_PATTERNS["recommendation"].search(block_content)
    if rec_match:
        result.recommendation = rec_match.group(1).strip()

    return result


def has_ralph_status_block(text: str) -> bool:
    """Check if text contains a RALPH_STATUS block."""
    return _STATUS_BLOCK_RE.search(text) is not None
