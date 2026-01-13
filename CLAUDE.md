# Claude Code Memory for takopi-ralph

## Critical Rules

### Plugin-Only Changes
**NEVER modify the takopi core package** (`/root/dev/takopi`). This is a plugin - all changes must be contained within the takopi-ralph repository. If a feature requires core changes, discuss with the user first to coordinate a proper PR to takopi.

### Architecture
- takopi-ralph is a **plugin** for takopi, not a standalone application
- It provides:
  - Engine backend: `ralph_engine` (autonomous coding loop)
  - Command backend: `ralph` (`/ralph` commands)
- Entry points are defined in `pyproject.toml`

## Project Structure
- `src/takopi_ralph/command/` - Command handlers for `/ralph`
- `src/takopi_ralph/engine/` - Engine runner for autonomous loop
- `src/takopi_ralph/prd/` - PRD management and validation
- `src/takopi_ralph/state/` - Loop state and circuit breaker

## Key Concepts

### Ralph Loop
- Each iteration runs with a **fresh Claude session** (no context accumulation)
- The PRD is the source of truth, not Claude's context window
- Circuit breaker protects against runaway loops

### PRD Schema
```python
class PRD:
    project_name: str
    goal: str
    stories: list[Story]  # NOT "tasks"
```

## Installation
```bash
uv tool install --reinstall --from /root/dev/takopi takopi --with /root/dev/takopi-ralph
systemctl restart takopi
```
