# takopi-ralph

**Autonomous Ralph coding loop plugin for [takopi](https://github.com/banteg/takopi)**

Ship features while you sleep. Ralph runs AI agents in a loop until all tasks are complete, with built-in safeguards to prevent runaway execution.

---

## Summary

**takopi-ralph** extends takopi with an autonomous coding loop system inspired by [Ralph](https://github.com/frankbria/ralph-claude-code). It provides:

- **Interactive requirements gathering** via Telegram inline keyboards
- **Autonomous loop execution** that implements features one story at a time
- **Circuit breaker protection** to halt when stuck
- **Progress tracking** with structured status reporting

The system works by:
1. Gathering requirements through `/ralph clarify`
2. Generating a `prd.json` with user stories
3. Running Claude in a loop, implementing one story per iteration
4. Analyzing responses for completion signals
5. Halting when all stories pass or the circuit breaker trips

---

## Quick Start

### 1. Install

```bash
# Install takopi-ralph
uv tool install takopi-ralph

# Or install from source
git clone https://github.com/yourname/takopi-ralph
cd takopi-ralph
uv pip install -e .
```

### 2. Configure

Add to `~/.takopi/takopi.toml`:

```toml
[ralph]
max_loops = 100

[plugins.ralph]
prd_path = "prd.json"
```

### 3. Gather Requirements

Start takopi and send:

```
/ralph clarify "Task management app"
```

Answer the questions via inline keyboard buttons. This generates `prd.json`.

### 4. Start the Loop

```
/ralph start
```

Ralph will autonomously implement each user story until complete.

### 5. Monitor Progress

```
/ralph status
```

---

## Features

### Engine Backend (`ralph`)

Wraps Claude with Ralph loop semantics:

- **Prompt augmentation** - Injects Ralph instructions and `---RALPH_STATUS---` block requirement
- **Response analysis** - Parses status blocks to detect completion, test-only loops, and errors
- **State persistence** - Tracks loop progress across restarts
- **Circuit breaker integration** - Stops execution when stuck

### Command Backend (`/ralph`)

| Command | Description |
|---------|-------------|
| `/ralph clarify <topic>` | Interactive requirements gathering via Telegram buttons |
| `/ralph start [project]` | Start the autonomous loop |
| `/ralph status` | Show loop progress and circuit breaker state |
| `/ralph stop` | Gracefully stop the loop |
| `/ralph reset [--all]` | Reset circuit breaker (add `--all` to clear state) |
| `/ralph help` | Show command help |

### Circuit Breaker

Prevents runaway token consumption using a state machine:

```
CLOSED ──(2 loops no progress)──> HALF_OPEN ──(threshold)──> OPEN
   ^                                    │
   └────(progress detected)─────────────┘
```

| Threshold | Default | Description |
|-----------|---------|-------------|
| `NO_PROGRESS_THRESHOLD` | 3 | Opens after N loops with no file changes |
| `SAME_ERROR_THRESHOLD` | 5 | Opens after N loops with repeated errors |

### Response Analyzer

Detects loop control signals:

1. **Structured parsing** - Extracts `---RALPH_STATUS---` blocks from Claude responses
2. **Text fallback** - Detects completion keywords when no status block
3. **Git integration** - Counts actual file changes via `git diff`
4. **Error filtering** - Two-stage filtering to avoid JSON field false positives

### `/ralph clarify` Flow

Interactive requirements gathering:

1. Presents questions as **inline keyboard buttons**
2. Categories: core requirements, users, integrations, edge cases, quality
3. Each answer updates the session state
4. Generates `prd.json` with user stories and acceptance criteria

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Telegram                                │
│  /ralph clarify → inline keyboards → answers → prd.json         │
│  /ralph start   → RalphRunner → Claude CLI → response analysis  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      takopi-ralph                               │
├─────────────────────────────────────────────────────────────────┤
│  Engine Backend                                                 │
│  ├── RalphRunner          Wraps Claude with loop semantics      │
│  ├── PromptAugmenter      Adds RALPH_STATUS requirement         │
│  └── ResponseAnalyzer     Parses status, detects exit signals   │
├─────────────────────────────────────────────────────────────────┤
│  Command Backend                                                │
│  ├── /ralph start         Initializes and runs loop             │
│  ├── /ralph clarify       Interactive requirements gathering    │
│  ├── /ralph status        Shows progress and circuit state      │
│  └── /ralph stop/reset    Loop control                          │
├─────────────────────────────────────────────────────────────────┤
│  State Management                                               │
│  ├── PRDManager           prd.json CRUD operations              │
│  ├── StateManager         Loop state persistence                │
│  └── CircuitBreaker       Runaway protection                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration Reference

### `[ralph]` section

```toml
[ralph]
# Maximum loop iterations before forced exit
max_loops = 100

# Claude model to use (optional, uses Claude default)
model = "sonnet"

# Allowed tools for Claude (optional)
allowed_tools = ["Bash", "Read", "Edit", "Write"]

# Circuit breaker thresholds
circuit_breaker_threshold = 3
error_threshold = 5
```

### `[plugins.ralph]` section

```toml
[plugins.ralph]
# Path to prd.json relative to project
prd_path = "prd.json"

# State directory for Ralph files
state_dir = ".ralph"

# Prompt template (default or custom path)
prompt_template = "default"
```

---

## prd.json Format

The Product Requirements Document tracks user stories:

```json
{
  "project_name": "My App",
  "description": "A task management application\nTarget users: End users\nScope: Basic CRUD",
  "created_at": "2026-01-10T12:00:00Z",
  "stories": [
    {
      "id": 1,
      "title": "Project Setup",
      "description": "Initialize project with basic structure",
      "acceptance_criteria": [
        "Project structure created",
        "Dependencies installed",
        "Basic configuration in place"
      ],
      "passes": false,
      "priority": 1,
      "notes": ""
    },
    {
      "id": 2,
      "title": "User Authentication",
      "description": "Implement JWT tokens authentication",
      "acceptance_criteria": [
        "Users can sign up",
        "Users can log in",
        "Sessions are secure",
        "Logout works correctly"
      ],
      "passes": false,
      "priority": 2,
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

## How It Works

### Loop Execution Flow

```
┌──────────────────────────────────────────────────────────────┐
│  1. Check circuit breaker (can_execute?)                     │
│                    │                                         │
│                    ▼                                         │
│  2. Load prd.json, get next_story()                          │
│                    │                                         │
│                    ▼                                         │
│  3. Augment prompt with Ralph instructions                   │
│                    │                                         │
│                    ▼                                         │
│  4. Run Claude CLI with augmented prompt                     │
│                    │                                         │
│                    ▼                                         │
│  5. Parse ---RALPH_STATUS--- from response                   │
│                    │                                         │
│                    ▼                                         │
│  6. Update circuit breaker (files_changed, has_errors)       │
│                    │                                         │
│                    ▼                                         │
│  7. Check exit conditions:                                   │
│     - EXIT_SIGNAL: true?                                     │
│     - All stories complete?                                  │
│     - Circuit breaker OPEN?                                  │
│                    │                                         │
│           ┌───────┴───────┐                                  │
│           │               │                                  │
│        Continue        Exit                                  │
│           │               │                                  │
│           └───────────────┘                                  │
└──────────────────────────────────────────────────────────────┘
```

### Clarify Flow

```
User: /ralph clarify "My App"
         │
         ▼
┌─────────────────────────────────────┐
│  "What is the minimum viable        │
│   version?"                         │
│                                     │
│  [Basic CRUD]                       │
│  [Full feature set]                 │
│  [Prototype only]                   │
│  [Skip]                             │
└─────────────────────────────────────┘
         │
         │ User taps button
         ▼
┌─────────────────────────────────────┐
│  Record answer, send next question  │
│  ... repeat for all questions ...   │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Build prd.json from answers        │
│  Save to project directory          │
│  "PRD saved! Run /ralph start"      │
└─────────────────────────────────────┘
```

---

## File Structure

After running Ralph, your project will have:

```
my-project/
├── prd.json                    # User stories (generated by /ralph clarify)
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

Or reset everything:
```
/ralph reset --all
```

### No RALPH_STATUS block in response

If Claude doesn't include the status block, the analyzer falls back to text analysis. This is less reliable. Check:

1. The prompt template includes status block instructions
2. Claude isn't truncating the response

### Loop exits immediately

Check:
1. prd.json exists and has stories with `passes: false`
2. Circuit breaker is CLOSED (`/ralph status`)
3. No syntax errors in prd.json

### Clarify session expired

Clarify sessions are stored temporarily. If you get "Session expired":
```
/ralph clarify "Your topic"  # Start a new session
```

---

## Development

### Setup

```bash
git clone https://github.com/yourname/takopi-ralph
cd takopi-ralph
uv sync --dev
```

### Run Tests

```bash
uv run pytest
```

### Lint

```bash
uv run ruff check .
uv run ruff format .
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
└── templates/           # Prompt templates
```

---

## Requirements

- Python 3.14+
- takopi >= 0.14
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)

---

## License

MIT

---

## Credits

- **Ralph concept**: [Geoffrey Huntley](https://ghuntley.com/ralph/) and [Ryan Carson](https://x.com/ryancarson)
- **ralph-claude-code**: [Frank Bria](https://github.com/frankbria/ralph-claude-code)
- **takopi**: [banteg](https://github.com/banteg/takopi)
