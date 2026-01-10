"""Pytest configuration and fixtures."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test state files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_prd_data():
    """Sample PRD data for testing."""
    return {
        "project_name": "Test Project",
        "description": "A test project",
        "stories": [
            {
                "id": 1,
                "title": "Setup project",
                "description": "Initialize the project",
                "acceptance_criteria": ["Project runs", "Tests pass"],
                "passes": False,
                "priority": 1,
            },
            {
                "id": 2,
                "title": "Add feature",
                "description": "Add the main feature",
                "acceptance_criteria": ["Feature works"],
                "passes": False,
                "priority": 2,
            },
        ],
    }


@pytest.fixture
def sample_ralph_response():
    """Sample Claude response with RALPH_STATUS block."""
    return """
I've implemented the project setup.

Created the following files:
- src/main.py
- tests/test_main.py

The basic structure is now in place.

---RALPH_STATUS---
STATUS: IN_PROGRESS
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 2
TESTS_STATUS: PASSING
WORK_TYPE: IMPLEMENTATION
EXIT_SIGNAL: false
RECOMMENDATION: Continue with feature implementation
---END_RALPH_STATUS---
"""


@pytest.fixture
def sample_complete_response():
    """Sample Claude response indicating completion."""
    return """
All tasks are complete!

---RALPH_STATUS---
STATUS: COMPLETE
TASKS_COMPLETED_THIS_LOOP: 1
FILES_MODIFIED: 0
TESTS_STATUS: PASSING
WORK_TYPE: DOCUMENTATION
EXIT_SIGNAL: true
RECOMMENDATION: All requirements met, project ready for review
---END_RALPH_STATUS---
"""
