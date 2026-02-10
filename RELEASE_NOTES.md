# Release: `bash` Tool — Rename, 30K Output, Persistent CWD

## The Problem

Nano-agents had a `run_command` tool that fell short in three ways that directly degraded agent performance:

### 1. Name misled agents
The name "run_command" implied a single, isolated command. Agents didn't realize they could chain with `&&`, `;`, pipes, or run scripts. In practice, agents would make 3 separate tool calls where one `npm install && npm test` would suffice — wasting turns and context window.

### 2. Output truncated at 8K characters
Test suites, build logs, and `grep` results routinely produce 10-20K of output. With an 8K cap, agents lost the critical tail of error messages — the exact part they needed to diagnose failures. They'd see the passing tests but miss the failure traceback at the end.

### 3. CWD reset every call
Each `run_command` call started fresh in the workspace root, regardless of any `cd` in the previous call. This forced agents to use absolute paths everywhere, making multi-step workflows unnatural:

```
# What agents had to do (verbose, fragile)
run_command("ls /project/src/auth")
run_command("cat /project/src/auth/middleware.py")
run_command("cd /project/src/auth && python -m pytest test_middleware.py")

# What they wanted to do (natural, like a human)
bash("cd src/auth")
bash("ls")
bash("cat middleware.py")
bash("python -m pytest test_middleware.py")
```

## What Changed

### Rename: `run_command` → `bash`
The tool is now called `bash`, matching Claude Code's naming convention. The `@function_tool` decorator auto-derives the tool name from the Python function name — no registration or config changes needed. The `on_tool_end` lifecycle hook uses dynamic `getattr(tool, 'name')`, so it works without modification.

The system prompt now documents multi-command capabilities:
```
- bash(command) — Execute shell commands, scripts, and multi-command pipelines
- Use bash for: installing deps, running tests, building, git, chained commands (&&, ;, |)
```

### Output cap: 8K → 30K characters
Matches Claude Code's Bash tool limit. Extracted magic numbers to named constants:
- `BASH_OUTPUT_MAX_CHARS = 30000`
- `BASH_OUTPUT_HEAD_RATIO = 0.6` (keep 60% from start)
- `BASH_OUTPUT_TAIL_RATIO = 0.35` (keep 35% from end)

The 5% gap between head+tail accommodates the `...(truncated)...` marker.

### Persistent CWD across calls
Each `bash()` call now tracks the shell's working directory. A shell wrapper appends a unique marker and `pwd` after the user's command:

```shell
user_command; __nano_exit=$?; echo "__NANO_CWD_f7e2a1__"; pwd; exit $__nano_exit
```

- The marker is stripped from output before returning to the agent
- Exit codes are preserved via `$?` capture before the marker
- CWD is stored in a `ContextVar` — async-safe, isolated per concurrent task
- Failed `cd` commands don't change CWD (shell exits before `pwd` runs in the original dir)
- `set_workspace()` resets CWD tracking when a new agent session begins
- Parser uses `rfind` (last occurrence) to handle edge cases where user output contains the marker string

## What Did NOT Change

| Component | Why safe |
|-----------|----------|
| `nano_agent.py` | `on_tool_end` reads tool name dynamically via `getattr(tool, 'name')` |
| `__main__.py` | `bash` is an internal agent tool, not an MCP-registered tool |
| `data_types.py` | No run_command-specific models existed |
| `web/server.py` | Zero tool name references — fully tool-agnostic |
| `web/static/index.html` | Zero tool name references |

## Live Verification

Qwen3-Coder 30B (Ollama) verified persistent CWD in 7 separate bash calls:

| Step | Command | CWD After |
|------|---------|-----------|
| 1 | `pwd` | `/tmp/nano-cwd-test` (workspace) |
| 2 | `cd /tmp` | `/tmp` |
| 3 | `pwd` | `/tmp` (persisted!) |
| 4 | `mkdir -p test_cwd_persist && cd test_cwd_persist` | `/tmp/test_cwd_persist` |
| 5 | `pwd` | `/tmp/test_cwd_persist` (persisted!) |
| 6 | `cd /nonexistent_dir_xyz` | `/tmp/test_cwd_persist` (unchanged after failure) |
| 7 | `pwd` | `/tmp/test_cwd_persist` (confirmed) |

## Test Coverage

19 new tests in `test_bash_tool.py`, all passing:

| Category | Count | What's tested |
|----------|-------|---------------|
| Constants | 3 | TOOL_BASH exists, in AVAILABLE_TOOLS, system prompt updated |
| Function | 2 | bash in tool list, basic execution |
| Output cap | 4 | Constants exist, no truncation <30K, truncation >30K, head/tail preserved |
| Persistent CWD | 7 | Defaults to workspace, persists after cd, unchanged after failed cd, marker stripped, exit code preserved, concurrent task isolation, reset on set_workspace |
| CWD parser | 3 | No marker, duplicate marker (uses last), invalid path rejected |

Zero regressions in full test suite (40 pre-existing failures unchanged).

## Files Changed

| File | Lines | What |
|------|-------|------|
| `modules/constants.py` | +4/-4 | Rename constant, update system prompt |
| `modules/nano_agent_tools.py` | +62/-14 | Rename function, output cap, CWD tracking |
| `tests/test_bash_tool.py` | +264 (new) | 19 tests |
| `CLAUDE.md` | +1/-1 | Reference update |
| `KNOWLEDGE_TRANSFER.md` | +4/-4 | Reference updates |
