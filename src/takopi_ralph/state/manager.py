"""State management for Ralph loops."""

from __future__ import annotations

import json
from pathlib import Path

from .models import LoopResult, LoopStatus, RalphState


class StateManager:
    """Manages Ralph state persistence."""

    def __init__(self, state_dir: Path | str = ".ralph"):
        self.state_dir = Path(state_dir)
        self.state_file = self.state_dir / "state.json"
        self.session_file = self.state_dir / "session.json"

    def _ensure_dir(self) -> None:
        """Ensure state directory exists."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def exists(self) -> bool:
        """Check if state file exists."""
        return self.state_file.exists()

    def load(self) -> RalphState:
        """Load state from file. Creates new state if not exists."""
        if not self.exists():
            return RalphState()

        content = self.state_file.read_text()
        data = json.loads(content)
        return RalphState.model_validate(data)

    def save(self, state: RalphState) -> None:
        """Save state to file."""
        self._ensure_dir()
        content = state.model_dump_json(indent=2)
        self.state_file.write_text(content)

    def update(self, result: LoopResult) -> RalphState:
        """Update state with a new loop result."""
        state = self.load()
        state.record_result(result)
        self.save(state)
        return state

    def start_session(
        self,
        project_name: str,
        session_id: str | None = None,
        max_loops: int = 100,
    ) -> RalphState:
        """Start a new Ralph session."""
        state = RalphState(
            project_name=project_name,
            session_id=session_id,
            status=LoopStatus.RUNNING,
            max_loops=max_loops,
        )
        self.save(state)
        return state

    def end_session(self, reason: str, status: LoopStatus = LoopStatus.COMPLETED) -> RalphState:
        """End the current session."""
        state = self.load()
        state.status = status
        state.exit_reason = reason
        self.save(state)
        return state

    def get_session_id(self) -> str | None:
        """Get the Claude session ID if stored."""
        if not self.session_file.exists():
            return None

        content = self.session_file.read_text()
        data = json.loads(content)
        return data.get("session_id")

    def set_session_id(self, session_id: str) -> None:
        """Store the Claude session ID."""
        self._ensure_dir()
        data = {"session_id": session_id}
        self.session_file.write_text(json.dumps(data, indent=2))

    def reset(self) -> None:
        """Reset all state files."""
        if self.state_file.exists():
            self.state_file.unlink()
        if self.session_file.exists():
            self.session_file.unlink()

    def is_running(self) -> bool:
        """Check if a Ralph loop is currently running."""
        if not self.exists():
            return False
        state = self.load()
        return state.status == LoopStatus.RUNNING

    def get_status_summary(self) -> str:
        """Get a human-readable status summary."""
        if not self.exists():
            return "No active Ralph session"

        state = self.load()
        lines = [
            f"Project: {state.project_name}",
            f"Status: {state.status.value}",
            f"Loop: {state.current_loop}/{state.max_loops}",
        ]

        if state.exit_reason:
            lines.append(f"Exit reason: {state.exit_reason}")

        if state.recent_results:
            last = state.recent_results[-1]
            lines.append(f"Last work: {last.work_type.value}")
            lines.append(f"Files modified: {last.files_modified}")

        return "\n".join(lines)
