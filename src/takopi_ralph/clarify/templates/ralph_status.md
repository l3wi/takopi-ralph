## RALPH STATUS REPORTING (CRITICAL)

At the END of your response, you MUST include this status block:

```
---RALPH_STATUS---
STATUS: IN_PROGRESS | COMPLETE | BLOCKED
TASKS_COMPLETED_THIS_LOOP: <number>
FILES_MODIFIED: <number>
TESTS_STATUS: PASSING | FAILING | NOT_RUN
WORK_TYPE: IMPLEMENTATION | TESTING | DOCUMENTATION | REFACTORING
EXIT_SIGNAL: false | true
RECOMMENDATION: <one-line summary of what to do next>
---END_RALPH_STATUS---
```

### When to set EXIT_SIGNAL: true
Set EXIT_SIGNAL to true when ALL of these conditions are met:
1. All tasks in prd.json are marked complete
2. All tests are passing (or no tests exist)
3. No errors in the last execution
4. You have nothing meaningful left to implement

### What NOT to do:
- Do NOT continue with busy work when EXIT_SIGNAL should be true
- Do NOT run tests repeatedly without implementing new features
- Do NOT refactor code that is already working fine
- Do NOT add features not in the specifications

## FEEDBACK LOOP ENFORCEMENT (BLOCKING)

Before committing ANY code, you MUST verify all feedback loops pass.
Run each command from prd.json feedback_commands:

{{feedback_commands_section}}

**COMMIT RULES:**
- Do NOT commit if ANY feedback loop fails
- Fix issues FIRST, then commit
- Each commit must leave the codebase in a working state
- If you cannot fix a failing test, do NOT commit - report BLOCKED status

## STEP SIZE GUIDELINES

Keep changes small and focused:

- **ONE logical change per loop** - Resist combining unrelated changes
- **Prefer multiple small commits** over one large commit
- **Run feedback loops after EACH change**, not at the end
- **If a task feels too large**, break it into subtasks first
- **Each commit should be independently reviewable**

## TASK PRIORITIZATION

When choosing what to work on, prioritize by risk and uncertainty:

| Priority | Category | Examples |
|----------|----------|----------|
| 1 (HIGH) | Architectural decisions | Core abstractions, data models, API contracts |
| 2 (HIGH) | Integration points | Module boundaries, external APIs, auth flows |
| 3 (HIGH) | Unknown unknowns | Spike work, proof of concepts, risky dependencies |
| 4 (MEDIUM) | Standard features | CRUD operations, UI components, business logic |
| 5 (LOW) | Polish and cleanup | Refactoring, quick wins, cosmetic fixes |
