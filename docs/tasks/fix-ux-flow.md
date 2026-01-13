# Task: Fix UX Flow and Command Interface

## Problem Summary

Based on real user testing, the current `/ralph` command flow has critical usability issues:

### Issues Observed

1. **PRD State Loss**: User ran `/ralph init`, Claude analyzed the repo and wrote to prd.json, but subsequent commands (`/ralph prd clarify`, `/ralph start`) showed "0 stories" or "PRD is empty"

2. **Stories Never Get Marked Complete**: The engine runner (`runner.py`) **never calls `prd_manager.mark_complete()`**. It only:
   - Updates `state.json` with loop results
   - Records circuit breaker metrics
   - But stories stay `passes=False` forever

3. **Confusing Command Structure**:
   - `/ralph init` vs `/ralph prd init` - unclear difference
   - `/ralph prd clarify` doesn't work as expected
   - No way to see "what will ralph actually do next?"

4. **Silent Failures**: PRDManager.load() returns empty PRD on any error (line 77-79 in manager.py), so users don't know their PRD is corrupted

---

## Root Cause Analysis

### 1. Engine Doesn't Update PRD

In `runner.py` lines 174-176:
```python
loop_result = analysis.to_loop_result()
self.state_manager.update(loop_result)
# ❌ No prd_manager.mark_complete() call
```

The engine analyzes the response and detects "TASKS_COMPLETED_THIS_LOOP: 1" in the status block, but never writes that back to `prd.json`.

### 2. Start Handler Relies on Engine to Update PRD

In `start.py` lines 159-166:
```python
prd = prd_manager.load()
if prd.all_complete():
    state_manager.end_session("All stories complete", LoopStatus.COMPLETED)
```

It expects the engine to have marked stories complete, but the engine never does.

### 3. Defensive Loading Hides Errors

In `manager.py` lines 77-79:
```python
except (json.JSONDecodeError, ValidationError, OSError):
    return PRD(project_name="", description="")
```

Any PRD corruption silently returns an empty PRD instead of alerting the user.

---

## Proposed Solutions

### Fix 1: Engine Must Update PRD When Stories Complete

**File:** `src/takopi_ralph/engine/runner.py`

The `ResponseAnalyzer` already extracts `TASKS_COMPLETED_THIS_LOOP` from the Claude response. We need to:

1. Parse which story IDs were completed (from the status block or response content)
2. Call `prd_manager.mark_complete(story_id)` for each

**New logic after line 176:**
```python
# If Claude reports completing the current story, mark it
if analysis.tasks_completed > 0 and current_story:
    self.prd_manager.mark_complete(current_story.id)
```

### Fix 2: Status Block Should Include Story ID

Currently the status block says:
```
TASKS_COMPLETED_THIS_LOOP: 1
```

It should say:
```
STORIES_COMPLETED: [1, 2]  # Story IDs
```

Update `prompt_augmenter.py` to instruct Claude to report specific story IDs.

### Fix 3: Simplify Command Structure

**Remove redundancy:**
- `/ralph init` → Unified initialization (PRD + loop)
- `/ralph prd` → View PRD status
- `/ralph prd clarify [focus]` → Add stories via LLM
- `/ralph start` → Begin/resume loop
- `/ralph stop` → Pause loop
- `/ralph status` → View loop state + PRD together

**Remove:**
- `/ralph prd init` (merge into `/ralph init`)

### Fix 4: Fail Loudly on PRD Errors

**File:** `src/takopi_ralph/prd/manager.py`

In `load()`, log warnings when falling back to empty PRD:
```python
except (json.JSONDecodeError, ValidationError, OSError) as e:
    logger.warning(f"PRD load failed: {e}, returning empty PRD")
    return PRD(project_name="", description="")
```

In handlers, use `load_strict()` for user-facing commands and show clear errors.

### Fix 5: Better Status Output

`/ralph status` should show:
```
## Ralph Status: obsidian-brain@main

### PRD (prd.json)
Project: Obsidian Brain
Stories: 5 total (3 complete, 2 pending)

Next up: Story #4 - Create MCP server integration
  → Acceptance criteria: 3 items

### Loop State (.ralph/state.json)
Status: PAUSED at loop 12
Last activity: 5 minutes ago
Exit reason: Safety limit reached

### Circuit Breaker
State: CLOSED (OK)
```

---

## Implementation Plan

### Phase 1: Fix Critical Bug (Engine → PRD sync) ✅ DONE

- [x] Update `runner.py` to call `mark_complete()` when story done
- [x] Update `ralph_status.md` template to request `CURRENT_STORY_COMPLETE` field
- [x] Update `status_parser.py` to parse `current_story_complete` from status block
- [x] Update `analyzer.py` to expose `current_story_complete` in `AnalysisResult`

### Phase 2: Improve Error Handling ✅ DONE

- [x] Add logging to `PRDManager.load()` fallback
- [x] Show validation errors in `/ralph status` output
- [x] Improve error messages in `/ralph init` when PRD exists but invalid

### Phase 3: Simplify Commands ✅ DONE

- [x] Improve `/ralph init` to validate existing PRD and show clearer options
- [x] Improve `/ralph status` output format with validation errors
- [x] Add `/ralph prd show` to dump raw PRD JSON

### Phase 4: Add Safeguards (Future)

- [ ] Validate PRD before `/ralph start`
- [ ] Warn if PRD has 0 stories
- [ ] Show diff of PRD changes after each loop

---

## Testing Scenarios

1. **Fresh start**: `/ralph init` → answer questions → `/ralph start` → loop completes a story → `/ralph status` shows story as complete

2. **Resume**: `/ralph start` runs 50 iterations → pauses → `/ralph start` resumes correctly

3. **Error recovery**: Corrupt prd.json → `/ralph status` shows clear error → `/ralph prd fix` repairs it

4. **Multi-story**: PRD has 5 stories → loop marks them complete one by one → exits when all done
