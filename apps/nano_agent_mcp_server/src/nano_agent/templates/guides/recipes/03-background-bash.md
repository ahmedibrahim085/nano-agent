# Recipe 03: Background Bash

Run long-running shell commands without blocking your workflow. Use `run_in_background` to execute build, test, or data processing tasks while continuing other work.

## Use Case

Use this when:
- Running test suites (pytest, Jest, RSpec, etc.)
- Building Docker images or application binaries
- Processing large datasets
- Running migrations or data transformation jobs
- Any task that takes longer than a few seconds

## Steps

### 1. Execute a Background Command

Use `Bash` with `run_in_background=True`:

```
Bash(
  command="cd /path/to/project && pytest tests/ -v --tb=short",
  run_in_background=True
)
```

This returns immediately with a `task_id` you can use to check status later.

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `command` | Yes | Shell command to execute |
| `run_in_background` | No | Set `True` for async execution |
| `timeout` | No | Max wait time in ms (up to 600000) |

> **Note**: There is no `working_dir` parameter. Use `cd /path && command` inside the command string.

### 2. Continue Working

The command runs in the background — proceed with other tasks:

```
# Tests are running... meanwhile:
Bash(command="cd /path/to/project && npm run lint")
```

### 3. Check Output Later

Use `TaskOutput` to check results:

```
TaskOutput(
  task_id="<task_id from step 1>",
  block=False
)
```

**Parameters:**
| Parameter | Default | Description |
|-----------|---------|-------------|
| `task_id` | (required) | The task ID returned by the background command |
| `block` | `True` | `True` = wait for completion; `False` = non-blocking status check |
| `timeout` | 30000 | Max wait time in ms |

## Example: Run Full Test Suite

**Scenario**: Start tests, continue implementing, then check results.

```
# Step 1: Start tests in background
Bash(
  command="cd /path/to/project && npm test -- --coverage",
  run_in_background=True
)
# Returns: task_id = "abc-123"

# Step 2: Continue with implementation while tests run
# ... edit files, write code ...

# Step 3: Check test results (non-blocking)
TaskOutput(task_id="abc-123", block=False)

# Step 4: Or wait for completion (blocking)
TaskOutput(task_id="abc-123", block=True)
```

## Example: Build Docker Image

```
# Start build in background
Bash(
  command="cd /path/to/project && docker build -t myapp:latest .",
  run_in_background=True
)
# Returns: task_id = "def-456"

# Write deployment docs while building...

# Check build status
TaskOutput(task_id="def-456", block=True)
```

## Example: Parallel Background Tasks

Run multiple tasks concurrently by launching several background commands:

```
# Start three tasks in parallel
Bash(command="cd /project && pytest tests/unit/ -v", run_in_background=True)
# task_id = "task-1"

Bash(command="cd /project && pytest tests/integration/ -v", run_in_background=True)
# task_id = "task-2"

Bash(command="cd /project && mypy src/ --strict", run_in_background=True)
# task_id = "task-3"

# Check all results later
TaskOutput(task_id="task-1", block=True)
TaskOutput(task_id="task-2", block=True)
TaskOutput(task_id="task-3", block=True)
```

## Important Notes

- **Cost**: Free — no LLM tokens used, pure shell execution
- **No AI reasoning**: This is direct shell execution, no LLM involved
- **No `working_dir`**: Use `cd /path && command` in the command string
- **Task ID**: Every background command returns a unique `task_id` for tracking
- **Timeout**: Default 2 minutes for foreground; use `timeout` parameter for longer

## When NOT to Use This Recipe

- For AI-powered tasks → use `prompt_nano_agent` (Recipe 01) or `launch_agent` (Recipe 04)
- For quick commands (<1 second) → use synchronous `Bash` without `run_in_background`
- When you need LLM integration → use a Teammate (Recipe 02) with nano-agent dispatch
