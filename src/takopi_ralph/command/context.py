"""Ralph context for project/branch targeting.

Provides RalphContext which holds the resolved working directory
and optional project/branch information from takopi.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from takopi.api import RunContext


@dataclass
class RalphContext:
    """Resolved project context for Ralph commands.

    Holds the working directory and optional project/branch info.
    All Ralph command handlers receive this context to know where
    to find prd.json, .ralph/ state, etc.

    Attributes:
        run_context: Takopi RunContext with project/branch (None if using cwd)
        cwd: Resolved working directory path
        args: Remaining args after project/branch parsing (e.g. ("start",) or ("prd", "clarify"))
    """

    run_context: RunContext | None
    cwd: Path
    args: tuple[str, ...] = ()

    @property
    def project(self) -> str | None:
        """Get the project name, if specified."""
        return self.run_context.project if self.run_context else None

    @property
    def branch(self) -> str | None:
        """Get the branch name, if specified."""
        return self.run_context.branch if self.run_context else None

    def context_label(self) -> str:
        """Get a human-readable label for the current context."""
        if self.run_context is None:
            return str(self.cwd.name)

        if self.branch:
            return f"{self.project}@{self.branch}"
        return self.project or str(self.cwd.name)
