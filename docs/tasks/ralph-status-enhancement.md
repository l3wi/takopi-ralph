# Task: Enhance /ralph status Command + Fix Loop Continuation Bug

## Context
The `/ralph status` command already intercepts the request and displays Ralph loop state without passing to AI. However, the user discovered that while status showed "in progress", the loop wasn't actually running - it was only executing ONE iteration.

## Bug Analysis: Loop Not Continuing

### Root Cause
1. `handle_start()` only called `run_one()` ONCE and returned
2. `RalphRunner.run_impl()` runs ONE iteration but nothing triggered the next
3. State showed "RUNNING" because `start_session()` set it, but no continuation occurred

### Fix Applied

#### 1. `engine/runner.py` - Fresh sessions each iteration
Ralph's design is to use **fresh Claude sessions** for each iteration. The PRD is the source of truth, not Claude's context window. Changes:
- Removed session ID storage (not needed)
- Removed resume/continuation prompt logic
- Always passes `resume=None` to inner runner
- Each iteration gets full PRD context in a fresh session

```python
# Always use fresh session (resume=None) - PRD is our state, not Claude's context
async for event in self.inner.run(augmented_prompt, None):
```

#### 2. `handlers/start.py` - Implement actual loop
Rewrote to run iterations in a loop until exit condition:
- Added `MAX_ITERATIONS_PER_START = 50` safety limit
- Loop checks circuit breaker before each iteration
- Checks state.status != RUNNING to detect /ralph stop or exit signals
- Updates prompt for continuations with current story info
- Checks PRD completion after each iteration
- Proper exit messages with iteration counts
- PAUSED state when hitting iteration limit (allows continuing Ralph state, but still uses fresh Claude sessions)

## Key Design Principle
**PRD is the source of truth, not Claude's context window.**

Each Ralph iteration:
1. Starts a FRESH Claude session
2. Loads the current PRD state
3. Gets full context about the project and current story
4. Works on the task
5. Updates PRD/state
6. Exits
7. Next iteration starts fresh with updated PRD

This prevents context window pollution and ensures each iteration has clean, focused context.

## Status Enhancement (Original Task)

### Changes Made to `handlers/status.py`

1. **Added helper functions:**
   - `_format_timestamp(dt)` - Formats datetime for display
   - `_format_duration(started_at, updated_at)` - Calculates and formats session duration

2. **Reorganized output sections:**
   - PRD section moved first (most important context)
   - Shows quality level
   - Shows next task with truncated description
   - Helpful prompts when no PRD exists

3. **Enhanced Loop State section:**
   - Started timestamp
   - Duration calculation
   - Consecutive counters (test-only, done signals, no progress)
   - Recent loops history (last 3 with status icons)

4. **Improved Circuit Breaker display:**
   - Changed indicators: OK/WARN/HALTED instead of colors

5. **Better empty state handling:**
   - Guides user to run `/ralph prd init` or `/ralph start`

## Acceptance Criteria
- [x] `/ralph status` does NOT pass to AI (already true)
- [x] Shows PRD existence and current story
- [x] Shows loop number and session info
- [x] Shows recent loop history summary
- [x] Shows circuit breaker health
- [x] Output is well-formatted and readable
- [x] Lint passes
- [x] Loop actually continues after first iteration
- [x] Each iteration uses fresh Claude session (PRD is source of truth)
- [x] Circuit breaker checked each iteration
- [x] Exit conditions properly detected
