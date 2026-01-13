"""Ralph runner that wraps an inner engine with loop semantics.

This runner augments prompts with Ralph instructions and
analyzes responses for loop control signals.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from takopi.api import BaseRunner, EventFactory, ResumeToken
from takopi.model import CompletedEvent, EngineId, TakopiEvent

from ..analysis import ResponseAnalyzer
from ..circuit_breaker import CircuitBreaker
from ..prd import PRDManager
from ..state import LoopStatus, StateManager
from .prompt_augmenter import build_ralph_prompt

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from takopi.runner import Runner

ENGINE: EngineId = EngineId("ralph_engine")


@dataclass
class RalphStreamState:
    """State tracking during a Ralph run."""

    factory: EventFactory = field(default_factory=lambda: EventFactory(ENGINE))
    loop_number: int = 0
    circuit_state: str = "CLOSED"
    last_answer: str = ""


class RalphRunner(BaseRunner):
    """Runner that wraps an inner engine with Ralph loop semantics.

    This runner:
    1. Augments prompts with Ralph instructions
    2. Delegates execution to an inner runner (e.g., ClaudeRunner)
    3. Analyzes responses for exit signals
    4. Updates state and circuit breaker
    """

    engine: EngineId = ENGINE

    def __init__(
        self,
        inner_runner: Runner,
        cwd: Path | None = None,
        max_loops: int = 100,
        prd_path: str = "prd.json",
        state_dir: str = ".ralph",
    ):
        """Initialize RalphRunner.

        Args:
            inner_runner: The Takopi runner to delegate execution to (e.g., ClaudeRunner)
            cwd: Working directory for the project
            max_loops: Maximum loop iterations before stopping
            prd_path: Path to prd.json relative to cwd
            state_dir: Directory for Ralph state files relative to cwd
        """
        self.inner = inner_runner
        self.cwd = cwd or Path.cwd()
        self.max_loops = max_loops

        # Initialize managers
        self.prd_manager = PRDManager(self.cwd / prd_path)
        self.state_manager = StateManager(self.cwd / state_dir)
        self.circuit_breaker = CircuitBreaker(self.cwd / state_dir)
        self.analyzer = ResponseAnalyzer(str(self.cwd))

    def format_resume(self, token: ResumeToken) -> str:
        """Format a resume token for display.

        Delegates to the inner runner since it owns the session.
        """
        return self.inner.format_resume(token)

    def is_resume_line(self, line: str) -> bool:
        """Check if a line contains a resume token.

        Delegates to the inner runner.
        """
        return self.inner.is_resume_line(line)

    def extract_resume(self, text: str | None) -> ResumeToken | None:
        """Extract a resume token from text.

        Delegates to the inner runner.
        """
        return self.inner.extract_resume(text)

    async def run_impl(
        self,
        prompt: str,
        resume: ResumeToken | None,
    ) -> AsyncIterator[TakopiEvent]:
        """Execute a Ralph loop iteration.

        This method:
        1. Checks circuit breaker
        2. Loads current state and PRD
        3. Augments the prompt with Ralph instructions
        4. Delegates to inner runner
        5. Analyzes the response
        6. Updates state and circuit breaker
        """
        state = RalphStreamState()

        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            cb_status = self.circuit_breaker.get_status()
            yield state.factory.completed_error(
                error=f"Circuit breaker is OPEN: {cb_status.get('reason', 'unknown')}",
                resume=resume,
            )
            return

        # Load state
        ralph_state = self.state_manager.load()
        state.loop_number = ralph_state.current_loop + 1
        state.circuit_state = self.circuit_breaker.get_state().value

        # Load PRD
        prd = self.prd_manager.load() if self.prd_manager.exists() else None
        current_story = prd.next_story() if prd else None

        # Build full prompt - Ralph always uses fresh sessions with full context
        # The PRD is the source of truth, not Claude's context window
        augmented_prompt = build_ralph_prompt(
            user_prompt=prompt,
            prd=prd,
            current_story=current_story,
            loop_number=state.loop_number,
            circuit_state=state.circuit_state,
        )

        # Delegate to inner runner and capture events
        # Always use fresh session (resume=None) - PRD is our state, not Claude's context
        captured_answer = ""
        captured_resume: ResumeToken | None = None

        async for event in self.inner.run(augmented_prompt, None):
            # Capture the answer from CompletedEvent for analysis
            if isinstance(event, CompletedEvent):
                captured_answer = event.answer
                captured_resume = event.resume

            # Pass through all events from inner runner
            yield event

        # Note: We intentionally do NOT store session ID for continuation.
        # Ralph uses fresh Claude sessions each iteration - the PRD is the
        # source of truth, not Claude's context window.

        # Analyze response after inner runner completes
        state.last_answer = captured_answer
        analysis = self.analyzer.analyze(state.last_answer, state.loop_number)

        # Update circuit breaker
        self.circuit_breaker.record_loop_result(
            loop_number=state.loop_number,
            files_changed=analysis.files_modified,
            has_errors=analysis.is_stuck,
            output_length=len(state.last_answer),
        )

        # CRITICAL: Mark story complete in PRD if Claude reports it's done
        logger.info(
            "Story completion check: current_story_complete=%s, current_story=%s",
            analysis.current_story_complete,
            current_story.id if current_story else None,
        )
        if analysis.current_story_complete and current_story:
            logger.info("Marking story %d as complete", current_story.id)
            self.prd_manager.mark_complete(current_story.id)

        # Update state
        loop_result = analysis.to_loop_result()
        self.state_manager.update(loop_result)

        # Check if should exit
        ralph_state = self.state_manager.load()
        should_exit, exit_reason = ralph_state.should_exit()

        if should_exit or analysis.exit_signal:
            reason = exit_reason or "Exit signal received"
            self.state_manager.end_session(reason, LoopStatus.COMPLETED)

        # Emit Ralph-specific completion info as a note (optional telemetry)
        # The actual CompletedEvent was already yielded from the inner runner
        if captured_resume:
            yield state.factory.action_completed(
                action_id=f"ralph.analysis.{state.loop_number}",
                kind="telemetry",
                title=f"Loop #{state.loop_number} analysis",
                ok=not analysis.is_stuck,
                detail={
                    "loop_number": state.loop_number,
                    "files_modified": analysis.files_modified,
                    "exit_signal": analysis.exit_signal,
                    "confidence": analysis.confidence_score,
                },
            )
