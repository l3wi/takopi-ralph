# takopi-ralph

**Autonomous coding loop plugin for [takopi](https://github.com/banteg/takopi)**

Ship features while you sleep. Ralph runs AI agents in a loop until all tasks are complete, with built-in safeguards to prevent runaway execution.

---

## Requirements

| Dependency | Version | Purpose |
|------------|---------|---------|
| Python | 3.14+ | Runtime |
| [takopi](https://github.com/banteg/takopi) | >= 0.15 | Telegram bot framework |
| [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) | Latest | AI agent backend |
| Git | Any | File change detection |

---

## Quick Start

### 1. Install

```bash
uv tool install takopi-ralph
```

Or from source:

```bash
git clone https://github.com/l3wi/takopi-ralph
cd takopi-ralph
uv pip install -e .
```

### 2. Configure

Add to `~/.takopi/takopi.toml`:

```toml
[ralph]
max_loops = 100
```

### 3. Initialize

Start takopi and send:

```
/ralph init
```

Answer the interactive questions to generate your `prd.json`.

### 4. Start

```
/ralph start
```

Ralph will autonomously implement each user story until complete.

---

## Lifecycle

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              LIFECYCLE                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  INIT                         LOOP                         EXIT          │
│  ────                         ────                         ────          │
│                                                                          │
│  /ralph init                  /ralph start                 Automatic     │
│       │                            │                            │        │
│       ▼                            ▼                            │        │
│  ┌─────────┐                 ┌───────────┐                      │        │
│  │ Answer  │                 │ Load PRD  │◄─────────────────────┤        │
│  │questions│                 │ next_story│                      │        │
│  └────┬────┘                 └─────┬─────┘                      │        │
│       │                            │                            │        │
│       ▼                            ▼                            │        │
│  ┌─────────┐                 ┌───────────┐                      │        │
│  │ Generate│                 │  Augment  │                      │        │
│  │ prd.json│                 │  prompt   │                      │        │
│  └─────────┘                 └─────┬─────┘                      │        │
│                                    │                            │        │
│                                    ▼                            │        │
│                              ┌───────────┐                      │        │
│                              │ Run Claude│                      │        │
│                              │    CLI    │                      │        │
│                              └─────┬─────┘                      │        │
│                                    │                            │        │
│                                    ▼                            │        │
│                              ┌───────────┐     ┌────────────┐   │        │
│                              │  Analyze  │────►│  Update    │   │        │
│                              │ response  │     │circuit brkr│   │        │
│                              └─────┬─────┘     └────────────┘   │        │
│                                    │                            │        │
│                                    ▼                            │        │
│                              ┌───────────┐                      │        │
│                              │Exit signal│──────────────────────┘        │
│                              │  check    │                               │
│                              └─────┬─────┘                               │
│                                    │ no                                  │
│                                    ▼                                     │
│                               Loop again                                 │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Init Phase

1. `/ralph init` starts an interactive session
2. Questions cover: core requirements, target users, integrations, edge cases, quality level
3. Answers are used to generate `prd.json` with user stories

### Loop Phase

1. Load `prd.json` and find the next incomplete story
2. Augment the prompt with Ralph instructions and `RALPH_STATUS` block requirements
3. Run Claude CLI with the augmented prompt
4. Parse the `---RALPH_STATUS---` block from Claude's response
5. Update circuit breaker state based on file changes and errors
6. Check exit conditions

### Exit Conditions

- `EXIT_SIGNAL: true` in status block
- All stories have `passes: true`
- Circuit breaker is `OPEN`
- Max loops reached
- 3+ consecutive test-only loops (test saturation)

---

## Context Targeting

Ralph supports targeting different projects and branches:

```
/ralph [project] [@branch] <command>
```

### Examples

| Command | Description |
|---------|-------------|
| `/ralph start` | Current directory |
| `/ralph myproject start` | Specific project |
| `/ralph @feature start` | Current project, feature worktree |
| `/ralph myproject @feature prd` | Project on feature branch |

### How It Works

1. **Project resolution**: Takopi resolves project aliases from your `takopi.toml`
2. **Branch resolution**: `@branch` targets git worktrees managed by takopi
3. **Fallback**: Without project/branch, uses current working directory

### Project Configuration

Projects are defined in your takopi config:

```toml
[projects.myproject]
path = "/path/to/myproject"
```

---

## Commands

| Command | Description |
|---------|-------------|
| `/ralph init` | Interactive project setup |
| `/ralph prd` | Show PRD status and progress |
| `/ralph prd init <desc>` | Create PRD from description |
| `/ralph prd clarify [focus]` | Analyze and improve PRD |
| `/ralph start` | Start the autonomous loop |
| `/ralph status` | Show loop progress and circuit state |
| `/ralph stop` | Gracefully stop the loop |
| `/ralph reset` | Reset circuit breaker |
| `/ralph reset --all` | Reset circuit breaker and clear state |
| `/ralph help` | Show command help |

---

## Monitoring Status

### Check Progress

```
/ralph status
```

Returns:
- Current loop number
- Stories completed / total
- Circuit breaker state (CLOSED/HALF_OPEN/OPEN)
- Last work type (IMPLEMENTATION/TESTING/etc.)
- Recent file changes

### State Files

Ralph creates a `.ralph/` directory in your project:

| File | Purpose |
|------|---------|
| `state.json` | Loop state, history, exit reason |
| `session.json` | Claude session ID for continuations |
| `circuit_breaker.json` | Circuit state and thresholds |
| `clarify_sessions.json` | Active clarify sessions |

### Debugging Stuck Loops

1. Check `/ralph status` for circuit breaker state
2. Review `.ralph/state.json` for loop history
3. Look at recent `RALPH_STATUS` blocks in conversation
4. If circuit breaker is OPEN, run `/ralph reset`

---

## Configuration

Add to `~/.takopi/takopi.toml`:

```toml
[ralph]
# Maximum loop iterations before forced exit
max_loops = 100

# Path to prd.json relative to project root
prd_path = "prd.json"

# Directory for Ralph state files
state_dir = ".ralph"

# Inner engine to use (only "claude" supported currently)
engine = "claude"
```

All options have sensible defaults. Minimal config:

```toml
[ralph]
max_loops = 100
```

---

## PRD Format

The Product Requirements Document (`prd.json`) tracks user stories:

```json
{
  "project_name": "My App",
  "description": "A task management application",
  "created_at": "2026-01-10T12:00:00Z",
  "branch_name": null,
  "quality_level": "production",
  "feedback_commands": {
    "typecheck": "bun run typecheck",
    "test": "bun run test",
    "lint": "bun run lint"
  },
  "stories": [
    {
      "id": 1,
      "title": "Project Setup",
      "description": "Initialize project with basic structure",
      "acceptance_criteria": [
        "Project structure created",
        "Dependencies installed"
      ],
      "passes": false,
      "priority": 1,
      "notes": ""
    }
  ]
}
```

### Story Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Unique story identifier |
| `title` | string | Short story title |
| `description` | string | Detailed description |
| `acceptance_criteria` | string[] | Conditions for completion |
| `passes` | bool | Whether story is complete |
| `priority` | int | Execution order (lower = higher priority) |
| `notes` | string | Optional notes from implementation |

### Quality Levels

| Level | Description |
|-------|-------------|
| `prototype` | Quick implementation, minimal tests |
| `production` | Full implementation with tests |
| `library` | Library-grade with comprehensive tests and docs |

### Feedback Commands

Customize validation commands for your stack:

```json
{
  "feedback_commands": {
    "typecheck": "bun run typecheck",
    "test": "pytest -q",
    "lint": "ruff check ."
  }
}
```

---

## RALPH_STATUS Block

Claude must include this block at the end of each response:

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

### Exit Signal Conditions

Set `EXIT_SIGNAL: true` when:
- All stories in prd.json have `passes: true`
- All tests are passing
- No errors in the last execution
- Nothing meaningful left to implement

---

## Circuit Breaker

Prevents runaway token consumption using a state machine:

```
CLOSED ──(2 loops no progress)──► HALF_OPEN ──(threshold)──► OPEN
   ▲                                    │
   └────(progress detected)─────────────┘
```

### States

| State | Description |
|-------|-------------|
| `CLOSED` | Normal operation, loop continues |
| `HALF_OPEN` | Warning state, monitoring for progress |
| `OPEN` | Loop halted, requires manual reset |

### Thresholds

| Threshold | Default | Description |
|-----------|---------|-------------|
| No progress | 3 | Opens after N loops with no file changes |
| Same error | 5 | Opens after N loops with repeated errors |

### Reset

```
/ralph reset         # Reset circuit breaker only
/ralph reset --all   # Reset circuit breaker and clear all state
```

---

## File Structure

After running Ralph, your project will have:

```
my-project/
├── prd.json                    # User stories (from /ralph init)
├── .ralph/
│   ├── state.json              # Loop state and history
│   ├── session.json            # Claude session ID
│   ├── circuit_breaker.json    # Circuit breaker state
│   └── clarify_sessions.json   # Active clarify sessions
└── ... your project files
```

---

## Troubleshooting

### Circuit Breaker is OPEN

The circuit breaker opens when:
- No file changes for 3+ consecutive loops
- Same error repeated 5+ times

**Fix:**
```
/ralph reset
```

### No RALPH_STATUS Block

If Claude doesn't include the status block, the analyzer falls back to text analysis. Check:
1. The prompt template includes status block instructions
2. Claude isn't truncating the response

### Loop Exits Immediately

Check:
1. `prd.json` exists and has stories with `passes: false`
2. Circuit breaker is CLOSED (`/ralph status`)
3. No syntax errors in `prd.json`

### Clarify Session Expired

Clarify sessions are stored temporarily. Start a new one:
```
/ralph init
```

---

## Development

### Setup

```bash
git clone https://github.com/l3wi/takopi-ralph
cd takopi-ralph
uv sync --dev
```

### Commands

```bash
uv run pytest              # Run tests with coverage
uv run ruff check .        # Lint
uv run ruff format .       # Format
```

### Package Structure

```
src/takopi_ralph/
├── engine/              # Engine backend (RalphRunner)
├── command/             # Command backend (/ralph)
│   └── handlers/        # Subcommand handlers
├── prd/                 # prd.json management
├── state/               # Loop state persistence
├── circuit_breaker/     # Runaway protection
├── analysis/            # Response parsing
├── clarify/             # Interactive requirements
│   └── templates/       # Prompt templates
└── init/                # Initialization flow
```

---

## License

MIT

---

## Credits

- **Ralph concept**: [Geoffrey Huntley](https://ghuntley.com/ralph/) and [Ryan Carson](https://x.com/ryancarson)
- **ralph-claude-code**: [Frank Bria](https://github.com/frankbria/ralph-claude-code)
- **takopi**: [banteg](https://github.com/banteg/takopi)
