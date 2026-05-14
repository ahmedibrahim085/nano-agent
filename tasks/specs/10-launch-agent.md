# Spec 10: Agent Identity (launch_agent Tool)

## Overview

The `launch_agent()` tool enables users to deploy AI agents with specific identities and expertise, separate from the project they're working on. Currently, `prompt_nano_agent()` combines agent identity with workspace context in a single tool, which makes it difficult to reuse agent personas across different projects. This feature introduces a new MCP tool that separates **agent identity** (WHO the agent is) from **workspace** (WHERE the agent works), allowing users to build a library of reusable agent personas that can be deployed to any project.

The implementation is intentionally simple: read `AGENT.md` from an `agent_path` directory, inject it as a layer in the system prompt, and reuse the existing agent execution infrastructure. No YAML frontmatter parsing, no new dependencies, no complex configuration — just plain Markdown files and clean layer separation. This feature unblocks future multi-agent team workflows where users can deploy specialized agents (backend expert, frontend specialist, QA engineer) to collaborate on the same project.

## Dependencies

### Prerequisites (Must Exist Before Building)
- Python 3.12+ environment with existing nano-agent v1.x codebase
- Existing modules: `constants.py`, `data_types.py`, `nano_agent.py`, `nano_agent_tools.py`
- `_execute_nano_agent_async()` function in `nano_agent.py` (lines 300-400)
- Existing `PromptNanoAgentResponse` schema in `data_types.py`

### Unblocked Features (What This Enables)
- **Multi-Agent Team Workflows** — Deploy multiple specialized agents to collaborate on projects
- **Agent Persona Library** — Build reusable agent identities for different roles and expertise
- **Project-Agnostic Agents** — Same agent identity can work on any project/workspace

## Design Decisions (from PRD Alignment)

These decisions were explicitly discussed and agreed upon during PRD planning. They are **BINDING** and must be followed exactly:

1. **Separate MCP tool**: `launch_agent()` is a new tool, separate from `prompt_nano_agent()` — different tool name, different schema
2. **agent_path is required**: Unlike workspace, agent_path MUST be provided (it's the whole point — identity is required)
3. **workspace is optional**: Defaults to cwd (same behavior as `prompt_nano_agent`)
4. **Two AGENT.md files possible**: agent_path/AGENT.md (identity) + workspace/AGENT.md (project rules) — both loaded if both exist
5. **No YAML frontmatter needed**: Just plain Markdown files. Keep it simple. No parsing complexity.
6. **No new dependencies**: Just file reading using `Path.read_text()` — stdlib only
7. **Reuses existing execution logic**: Internally calls `_execute_nano_agent_async()` after building layered instructions
8. **prompt_nano_agent stays unchanged**: Zero modifications to existing tool — completely separate implementation
9. **Same response schema**: Returns `PromptNanoAgentResponse` (same as `prompt_nano_agent`)
10. **agent_path validated**: Must exist and contain AGENT.md, otherwise return error (not graceful skip — this is required)

## Architecture

### System Prompt Assembly

The `launch_agent()` tool builds a 3-layer system prompt:

```
## Base Instructions
{NANO_AGENT_SYSTEM_PROMPT — always included from constants.py}

## Agent Instructions
{From agent_path/AGENT.md — agent's identity, expertise, role}

## Project Instructions
{From workspace/AGENT.md — project-specific rules, if exists}

Workspace directory: /path/to/workspace
```

**Layer Order** (base first, project last):
1. **Base Instructions** — Always included, defines agent capabilities and tools
2. **Agent Instructions** — Identity and expertise from `agent_path/AGENT.md` (required)
3. **Project Instructions** — Project-specific rules from `workspace/AGENT.md` (optional)

### File Structure

Users organize agent identities in a directory structure:

```
Ai_Teams/
  member1/
    AGENT.md       → "You are a Python backend expert. Focus on API design..."
  member2/
    AGENT.md       → "You are a frontend React specialist. Focus on components..."
  member3/
    AGENT.md       → "You are a QA engineer. Always write tests first..."

Projects/
  my-app/
    AGENT.md       → "This is a TypeScript project. Use strict mode..."
    src/
    tests/
```

**Usage Example**:
```python
# Deploy member1 (Python backend expert) to work on my-app
mcp__nano_agent__launch_agent(
    agentic_prompt="Build the REST API for user management",
    agent_path="/Users/ahmedmaged/ai_storage/Ai_Teams/member1",
    workspace="/Users/ahmedmaged/projects/my-app",
    model="glm-4.7",
    provider="zai"
)
```

### Tool Comparison

| Aspect | `prompt_nano_agent()` | `launch_agent()` |
|--------|----------------------|------------------|
| **Purpose** | Single-call agent execution | Identity-aware agent deployment |
| **Agent Identity** | Implicit (same prompt for all) | Explicit from `agent_path/AGENT.md` |
| **Workspace** | Optional (defaults to cwd) | Optional (defaults to cwd) |
| **Project Rules** | None (future: US-001) | Loads workspace/AGENT.md |
| **System Prompt** | Base only | Base + Agent + Project |
| **Use Case** | Quick tasks, one-off agents | Reusable agent personas, teams |

### MCP Tool Registration

Following the pattern from `__main__.py` line 41:

```python
# Existing registration
mcp.tool()(prompt_nano_agent)

# New registration (same pattern)
from .modules.nano_agent import launch_agent
mcp.tool()(launch_agent)
```

## Implementation Phases

### Phase A: Agent Identity Loader
**Objective**: Create module to read AGENT.md from agent_path and build layered system prompt

#### Sub-Tasks (Nano-Agent Delegation Ready)

##### Sub-Task A1: Create LaunchAgentRequest in data_types.py
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/data_types.py`
- **What to implement**:
  - Add new Pydantic model `LaunchAgentRequest` after `PromptNanoAgentRequest` (after line 33)
  - Fields:
    - `agentic_prompt: str` (required, same as PromptNanoAgentRequest)
    - `agent_path: str` (required, min_length=1, description="Path to directory containing AGENT.md")
    - `workspace: Optional[str] = None` (optional, same as PromptNanoAgentRequest)
    - `model: str = "gpt-5-mini"` (optional, same as PromptNanoAgentRequest)
    - `provider: Literal["openai", "anthropic", "ollama", "lmstudio", "zai"] = "openai"` (optional)
  - Add docstring explaining the model
- **Existing patterns to follow**:
  - Follow `PromptNanoAgentRequest` structure exactly (lines 14-33)
  - Use same Field() parameters: `description`, `min_length`, `default`
  - Use same Literal type for provider
- **Acceptance criteria**:
  - `LaunchAgentRequest` model validates correctly
  - `agent_path` is required (no default value)
  - `workspace` defaults to None
  - Pydantic validation enforces string constraints
- **Example input → output**:
  - Input: `LaunchAgentRequest(agentic_prompt="Build API", agent_path="/agents/backend", workspace="/project")`
  - Output: Valid model instance with all fields set correctly

##### Sub-Task A2: Create agent_identity.py module
- **File to create**: `apps/nano_agent_mcp_server/src/nano_agent/modules/agent_identity.py`
- **What to implement**:
  - Module docstring explaining the agent identity loader
  - Import statements: `pathlib.Path`, `logging`
  - Define `read_agent_instructions(agent_path: str) -> str` function
  - Define `build_layered_prompt(agent_instructions: str, agent_path: str, workspace: str | None) -> str` function
  - Use `logger = logging.getLogger(__name__)` pattern
- **Existing patterns to follow**:
  - Follow module structure from `constants.py` (lines 1-15: docstring, imports, constants)
  - Follow logging pattern from `provider_config.py` line 18
  - Follow file reading pattern from `nano_agent_tools.py` `read_file()` (lines 20-50)
- **Acceptance criteria**:
  - Module imports without errors
  - `read_agent_instructions()` function reads AGENT.md from agent_path
  - `build_layered_prompt()` function assembles 3-layer prompt
  - Appropriate logging for debug and errors
- **Example input → output**:
  - Input: `read_agent_instructions("/agents/member1")` where `/agents/member1/AGENT.md` contains "You are a Python expert"
  - Output: `"You are a Python expert"`
  - Input: `build_layered_prompt("You are a Python expert", "/agents/member1", "/project")` where `/project/AGENT.md` contains "Use TypeScript"
  - Output: `"## Base Instructions\n{NANO_AGENT_SYSTEM_PROMPT}\n\n## Agent Instructions\nYou are a Python expert\n\n## Project Instructions\nUse TypeScript"`

##### Sub-Task A3: Implement read_agent_instructions function
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/agent_identity.py`
- **What to implement**:
  - `def read_agent_instructions(agent_path: str) -> str:`
  - Validate agent_path exists: `path = Path(agent_path); if not path.exists(): raise ValueError(f"Agent path does not exist: {agent_path}")`
  - Validate AGENT.md exists: `agent_file = path / "AGENT.md"; if not agent_file.exists(): raise ValueError(f"AGENT.md not found in: {agent_path}")`
  - Read file: `content = agent_file.read_text(encoding="utf-8")`
  - Log debug: `logger.debug(f"Read agent instructions from {agent_file}")`
  - Return content (strip leading/trailing whitespace)
  - Handle read errors: try/except with `OSError` and re-raise with context
- **Existing patterns to follow**:
  - Follow file validation pattern from `read_file()` in `nano_agent_tools.py` (lines 20-50)
  - Use `Path.exists()` and `Path.read_text()` for file operations
  - Use `ValueError` for validation failures (consistent with existing codebase)
- **Acceptance criteria**:
  - Raises `ValueError` if agent_path doesn't exist
  - Raises `ValueError` if AGENT.md doesn't exist in agent_path
  - Returns file content as string
  - Handles encoding errors gracefully
  - Logs appropriate debug messages
- **Example input → output**:
  - Input: `read_agent_instructions("/agents/member1")` where path exists and has AGENT.md
  - Output: `"You are a Python backend expert..."`
  - Input: `read_agent_instructions("/nonexistent")`
  - Output: Raises `ValueError("Agent path does not exist: /nonexistent")`
  - Input: `read_agent_instructions("/agents/empty")` where directory exists but no AGENT.md
  - Output: Raises `ValueError("AGENT.md not found in: /agents/empty")`

##### Sub-Task A4: Implement build_layered_prompt function
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/agent_identity.py`
- **What to implement**:
  - `def build_layered_prompt(agent_instructions: str, agent_path: str, workspace: str | None) -> str:`
  - Import `NANO_AGENT_SYSTEM_PROMPT` from `.constants`
  - Start with base: `prompt = f"## Base Instructions\n{NANO_AGENT_SYSTEM_PROMPT}"`
  - Add agent layer: `prompt += f"\n\n## Agent Instructions\n{agent_instructions}"`
  - Add project layer if workspace/AGENT.md exists AND workspace != agent_path (avoid duplication):
    - `if workspace: workspace_agent_file = Path(workspace) / "AGENT.md"; if workspace_agent_file.exists(): project_instructions = workspace_agent_file.read_text(encoding="utf-8"); prompt += f"\n\n## Project Instructions\n{project_instructions}"`
  - **Do NOT add "Workspace directory:" here** — the existing code in `_execute_nano_agent_async()` (line 349) already appends it. Adding it here would cause duplication.
  - Log info when project instructions loaded
  - Return assembled prompt
- **Existing patterns to follow**:
  - Follow string concatenation pattern from `nano_agent.py` line 348
  - Use same section header format: `## Section Name\n{content}`
  - Use `Path.cwd()` for default workspace (same as `prompt_nano_agent`)
- **Acceptance criteria**:
  - Base instructions always included first
  - Agent instructions always included (required parameter)
  - Project instructions included only if workspace/AGENT.md exists
  - Section headers match format: `## Base Instructions`, `## Agent Instructions`, `## Project Instructions`
  - No "Workspace directory:" appended (handled by caller)
- **Example input → output**:
  - Input: `build_layered_prompt("You are a Python expert", "/agents/member1", "/project")` where `/project/AGENT.md` exists with "Use strict mode"
  - Output: `"## Base Instructions\n{NANO_AGENT_SYSTEM_PROMPT}\n\n## Agent Instructions\nYou are a Python expert\n\n## Project Instructions\nUse strict mode"`
  - Input: `build_layered_prompt("You are a QA engineer", "/agents/qa", None)` (no workspace)
  - Output: `"## Base Instructions\n{NANO_AGENT_SYSTEM_PROMPT}\n\n## Agent Instructions\nYou are a QA engineer"`

##### Sub-Task A5: Create launch_agent function in nano_agent.py
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/nano_agent.py`
- **What to implement**:
  - Add `async def launch_agent(agentic_prompt: str, agent_path: str, workspace: str = "", model: str = DEFAULT_MODEL, provider: str = DEFAULT_PROVIDER, ctx: Any = None) -> Dict[str, Any]:`
  - Add after `prompt_nano_agent()` function (after line 650+)
  - Import `LaunchAgentRequest` from `.data_types`
  - Import `read_agent_instructions`, `build_layered_prompt` from `.agent_identity`
  - Function signature matches MCP tool pattern (same as `prompt_nano_agent`)
  - Validate request: `request = LaunchAgentRequest(agentic_prompt=agentic_prompt, agent_path=agent_path, workspace=workspace or None, model=model, provider=provider)`
  - Read agent identity: `agent_instructions = read_agent_instructions(request.agent_path)`
  - Build layered prompt: `layered_prompt = build_layered_prompt(agent_instructions, request.agent_path, request.workspace)`
  - Create internal PromptNanoAgentRequest: `internal_request = PromptNanoAgentRequest(agentic_prompt=request.agentic_prompt, model=request.model, provider=request.provider, workspace=request.workspace)`
  - Execute agent with override: `response = await _execute_nano_agent_async(internal_request, instructions_override=layered_prompt, enable_rich_logging=(ctx is None))`
  - Handle progress reporting if ctx available (same as `prompt_nano_agent`)
  - Return `response.model_dump()`
  - Handle exceptions and return error response
- **Existing patterns to follow**:
  - Follow `prompt_nano_agent()` structure exactly (lines 576-650)
  - Use same progress reporting: `ctx.report_progress()`, `ctx.info()`, `ctx.error()`
  - Use same error handling pattern
  - Use same response conversion: `response.model_dump()`
- **Acceptance criteria**:
  - Function signature matches MCP tool requirements
  - Agent identity loaded from agent_path/AGENT.md
  - Layered prompt built correctly
  - Agent executes with custom instructions
  - Progress reported via ctx if available
  - Returns dict with same structure as `prompt_nano_agent`
- **Example input → output**:
  - Input: `await launch_agent("Build API", "/agents/backend", "/project", "glm-4.7", "zai")`
  - Output: `{"success": True, "result": "API built successfully", "metadata": {...}, "execution_time_seconds": 45.2}`

##### Sub-Task A6: Add instructions_override parameter to execution functions
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/nano_agent.py`
- **What to implement**:
  - Add `instructions_override: str | None = None` parameter to `_execute_nano_agent_async()` (line ~300)
  - Add same parameter to `_execute_nano_agent()` (sync version, line ~431)
  - In both functions, around the instruction building line (348 async, 485 sync), check:
    ```python
    if instructions_override:
        instructions = instructions_override + f"\n\nWorkspace directory: {workspace_path}\n"
    else:
        instructions = NANO_AGENT_SYSTEM_PROMPT + f"\n\nWorkspace directory: {workspace_path}\n"
    ```
  - This is simpler than ContextVar — explicit parameter passing, no side-effects
- **Why parameter over ContextVar**:
  - More explicit and readable — no hidden state
  - Easier to test — just pass a parameter
  - No additional file modifications (no changes to nano_agent_tools.py)
  - Follows Python best practice: "explicit is better than implicit"
- **Existing patterns to follow**:
  - Follow existing `enable_rich_logging` parameter pattern (already on both functions)
  - Use `Optional[str]` with default `None`
- **Acceptance criteria**:
  - Both async and sync functions accept `instructions_override` parameter
  - When `None` (default), uses NANO_AGENT_SYSTEM_PROMPT (backward compatible)
  - When set, uses the override string as base instructions
  - `prompt_nano_agent()` calls with `instructions_override=None` (unchanged)
  - `launch_agent()` calls with `instructions_override=layered_prompt`
- **Example input → output**:
  - Input: `_execute_nano_agent_async(request, instructions_override="## Custom\nCustom instructions")`
  - Output: Agent executes with custom instructions + workspace dir
  - Input: `_execute_nano_agent_async(request)` (no override)
  - Output: Agent executes with default NANO_AGENT_SYSTEM_PROMPT (backward compatible)

##### Sub-Task A8: Register launch_agent as MCP tool in __main__.py
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/__main__.py`
- **What to implement**:
  - Import `launch_agent` from `.modules.nano_agent` (after line 17, where `prompt_nano_agent` is imported)
  - Register as MCP tool: `mcp.tool()(launch_agent)` (after line 41, where `prompt_nano_agent` is registered)
  - Update MCP server instructions docstring to mention both tools
- **Existing patterns to follow**:
  - Follow import pattern from line 17: `from .modules.nano_agent import prompt_nano_agent`
  - Follow registration pattern from line 41: `mcp.tool()(prompt_nano_agent)`
  - Update docstring to match existing style
- **Acceptance criteria**:
  - `launch_agent` imported successfully
  - Registered as MCP tool
  - MCP server exposes both `prompt_nano_agent` and `launch_agent`
  - Docstring updated to mention both tools
- **Example input → output**:
  - Input: Start MCP server and list tools
  - Output: Both `prompt_nano_agent` and `launch_agent` appear in tool list

##### Sub-Task A9: Write comprehensive tests
- **File to create**: `apps/nano_agent_mcp_server/tests/test_agent_identity.py`
- **What to implement**:
  - `test_read_agent_instructions_success()` → verify successful reading of AGENT.md
  - `test_read_agent_instructions_path_not_found()` → verify ValueError for missing path
  - `test_read_agent_instructions_agent_md_not_found()` → verify ValueError for missing AGENT.md
  - `test_read_agent_instructions_encoding_error()` → verify handling of encoding errors
  - `test_build_layered_prompt_base_only()` → verify base + agent layers (no workspace)
  - `test_build_layered_prompt_with_workspace()` → verify all 3 layers
  - `test_build_layered_prompt_workspace_no_agent_md()` → verify graceful handling when workspace has no AGENT.md
  - `test_build_layered_prompt_same_path()` → verify dedup when agent_path == workspace (single load)
  - `test_launch_agent_success()` → integration test for successful agent launch
  - `test_launch_agent_invalid_agent_path()` → verify error handling for invalid path
  - `test_launch_agent_backward_compatible()` → verify prompt_nano_agent still works
- **Existing patterns to follow**:
  - Follow test structure from existing tests (if any exist in project)
  - Use `pytest` and `tmp_path` fixture for file system tests
  - Use `pytest.raises` for exception testing
- **Acceptance criteria**:
  - All tests pass
  - Test coverage >90% for agent_identity module
  - Edge cases covered (missing files, encoding errors, etc.)

## Acceptance Criteria

Full checklist from PRD US-010, expanded with technical details:

- [ ] **New MCP tool implemented**: `launch_agent(agentic_prompt, agent_path, workspace, provider, model)` registered and callable
- [ ] **agent_path is required**: LaunchAgentRequest validates agent_path is present (no default value)
- [ ] **Agent reads agent_path/AGENT.md**: `read_agent_instructions()` loads identity from agent directory
- [ ] **Agent Instructions layer included**: System prompt contains `## Agent Instructions` with agent identity
- [ ] **workspace/AGENT.md loaded if exists**: `build_layered_prompt()` checks for and loads project rules
- [ ] **System prompt layers correct**: Base → Agent Instructions → Project Instructions → Workspace dir
- [ ] **agent_path validated**: ValueError raised if path doesn't exist or AGENT.md not found
- [ ] **Instruction files are plain Markdown**: No YAML parsing, just `Path.read_text()`
- [ ] **Reuses existing execution infrastructure**: Calls `_execute_nano_agent_async()` with `instructions_override` parameter
- [ ] **Separate from prompt_nano_agent**: Different function, different request model, zero modifications to prompt_nano_agent
- [ ] **Response uses same schema**: Returns `PromptNanoAgentResponse` converted to dict
- [ ] **Tests for all scenarios**: Agent loading, workspace loading, both loaded, missing AGENT.md, agent_path validation
- [ ] **No new dependencies**: Uses only stdlib (pathlib, logging)

## Scenarios

### Happy Path

#### Scenario 1: Agent with identity only (no workspace AGENT.md)
**Input**:
```python
await launch_agent(
    "Build a REST API for user management",
    agent_path="/Users/ahmedmaged/ai_storage/Ai_Teams/member1",
    workspace="/Users/ahmedmaged/projects/my-app",
    model="glm-4.7",
    provider="zai"
)

# /Users/ahmedmaged/ai_storage/Ai_Teams/member1/AGENT.md:
# "You are a Python backend expert. Focus on API design, database modeling,
#  and writing clean, testable code with FastAPI."
```

**Expected Behavior**:
1. `LaunchAgentRequest` validates successfully
2. `read_agent_instructions()` reads `/Users/ahmedmaged/ai_storage/Ai_Teams/member1/AGENT.md`
3. `build_layered_prompt()` assembles:
   - Base Instructions (NANO_AGENT_SYSTEM_PROMPT)
   - Agent Instructions ("You are a Python backend expert...")
   - No Project Instructions (workspace/AGENT.md doesn't exist)
   - Workspace directory: /Users/ahmedmaged/projects/my-app
4. `_execute_nano_agent_async()` called with `instructions_override=layered_prompt`
5. Agent executes with custom instructions
6. Agent builds REST API with Python backend expertise
7. Response: `{"success": True, "result": "REST API built...", ...}`

#### Scenario 2: Agent with identity + workspace project rules
**Input**:
```python
await launch_agent(
    "Add authentication to the API",
    agent_path="/Users/ahmedmaged/ai_storage/Ai_Teams/member1",
    workspace="/Users/ahmedmaged/projects/my-app",
    model="glm-4.7",
    provider="zai"
)

# /Users/ahmedmaged/projects/my-app/AGENT.md:
# "This is a TypeScript project. Use strict mode, follow our naming
#  conventions, and run tests before committing."
```

**Expected Behavior**:
1. Both agent_path/AGENT.md and workspace/AGENT.md exist
2. `build_layered_prompt()` assembles all 3 layers:
   - Base Instructions
   - Agent Instructions ("You are a Python backend expert...")
   - Project Instructions ("This is a TypeScript project...")
   - Workspace directory
3. Agent executes with both identity and project context
4. Agent adds authentication aware of both backend expertise and project rules

#### Scenario 3: Agent path same as workspace path
**Input**:
```python
await launch_agent(
    "Refactor the codebase",
    agent_path="/Users/ahmedmaged/projects/my-app",
    workspace="/Users/ahmedmaged/projects/my-app",
    model="qwen3-coder:30b",
    provider="ollama"
)

# /Users/ahmedmaged/projects/my-app/AGENT.md:
# "You are a code refactoring expert. Focus on clean code principles..."
```

**Expected Behavior**:
1. agent_path and workspace point to same directory
2. Same AGENT.md serves as agent identity
3. `build_layered_prompt()` detects agent_path == workspace and SKIPS Project Instructions layer (avoids duplicate content)
4. System prompt includes Base + Agent Instructions only (no duplicate)
5. Agent refactors codebase with expertise defined in AGENT.md

### Negative Cases

#### Scenario 1: agent_path doesn't exist
**Input**:
```python
await launch_agent(
    "Build API",
    agent_path="/nonexistent/path",
    workspace="/project"
)
```

**Expected Behavior**:
1. `LaunchAgentRequest` validates successfully (Pydantic doesn't check path existence)
2. `read_agent_instructions("/nonexistent/path")` called
3. `Path("/nonexistent/path").exists()` returns False
4. `ValueError` raised: `"Agent path does not exist: /nonexistent/path"`
5. Exception caught in `launch_agent()`
6. Error response returned: `{"success": False, "error": "Agent path does not exist: /nonexistent/path", ...}`

#### Scenario 2: agent_path exists but no AGENT.md
**Input**:
```python
# Directory exists but no AGENT.md
await launch_agent(
    "Build API",
    agent_path="/tmp/empty_dir",
    workspace="/project"
)
```

**Expected Behavior**:
1. `read_agent_instructions("/tmp/empty_dir")` called
2. `Path("/tmp/empty_dir").exists()` returns True
3. `(Path("/tmp/empty_dir") / "AGENT.md").exists()` returns False
4. `ValueError` raised: `"AGENT.md not found in: /tmp/empty_dir"`
5. Exception caught in `launch_agent()`
6. Error response returned: `{"success": False, "error": "AGENT.md not found in: /tmp/empty_dir", ...}`

#### Scenario 3: workspace AGENT.md has read error (graceful skip)
**Input**:
```python
# workspace/AGENT.md exists but has permission issues
await launch_agent(
    "Build API",
    agent_path="/agents/backend",
    workspace="/restricted/project"  # AGENT.md exists but unreadable
)
```

**Expected Behavior**:
1. `read_agent_instructions("/agents/backend")` succeeds
2. `build_layered_prompt()` attempts to read `/restricted/project/AGENT.md`
3. `Path.read_text()` raises `PermissionError` or `OSError`
4. Exception caught in `build_layered_prompt()`
5. Warning logged: "Failed to read workspace AGENT.md: {error}"
6. Prompt assembled without Project Instructions layer
7. Agent executes with Base + Agent Instructions only
8. Response: `{"success": True, ...}` (graceful degradation)

### Edge Cases

#### Scenario 1: Very large AGENT.md (>10KB)
**Input**:
```python
# /agents/expert/AGENT.md is 15KB of detailed instructions
await launch_agent(
    "Complex task",
    agent_path="/agents/expert"
)
```

**Expected Behavior**:
1. `read_agent_instructions()` reads entire 15KB file
2. No size limit enforced (file is reasonable)
3. Warning logged: "Large AGENT.md file (15KB), may impact token usage"
4. Entire content included in system prompt
5. Agent executes with large instruction set
6. Token tracking reflects increased input tokens

#### Scenario 2: Unicode in AGENT.md
**Input**:
```python
# /agents/expert/AGENT.md contains:
# "Handle: 中文, 日本語, 한국어, emoji 🚀, special chars: <>&''\""
await launch_agent(
    "Task",
    agent_path="/agents/expert"
)
```

**Expected Behavior**:
1. File read with UTF-8 encoding (default)
2. Unicode characters preserved correctly
3. System prompt includes all Unicode characters
4. Agent receives instructions with proper encoding
5. No encoding errors or character corruption

#### Scenario 3: agent_path is relative path (resolve to absolute)
**Input**:
```python
await launch_agent(
    "Task",
    agent_path="../agents/backend",  # Relative path
    workspace="./project"
)
```

**Expected Behavior**:
1. `Path("../agents/backend")` resolved relative to current working directory
2. `Path.exists()` checks resolved absolute path
3. AGENT.md read from resolved absolute path
4. Info logged: "Resolved agent path: /absolute/path/to/agents/backend"
5. Agent executes successfully

## Test Plan

### Unit Tests (test_agent_identity.py)

| Test Function | Verifies | Key Assertions |
|---------------|----------|----------------|
| `test_read_agent_instructions_success()` | Successful file reading | Asserts returns content, content matches file, debug log emitted |
| `test_read_agent_instructions_path_not_found()` | Missing path error | Asserts raises ValueError, error message contains path |
| `test_read_agent_instructions_agent_md_not_found()` | Missing AGENT.md error | Asserts raises ValueError, error message mentions AGENT.md |
| `test_read_agent_instructions_encoding_error()` | Encoding error handling | Asserts raises ValueError with encoding context |
| `test_build_layered_prompt_base_only()` | Base + agent layers | Asserts prompt starts with "## Base Instructions", includes "## Agent Instructions", no "## Project Instructions" |
| `test_build_layered_prompt_with_workspace()` | All 3 layers | Asserts all 3 section headers present, correct order, no workspace dir appended |
| `test_build_layered_prompt_workspace_no_agent_md()` | Graceful workspace handling | Asserts no "## Project Instructions" when file missing, agent layer still present |
| `test_build_layered_prompt_same_path()` | Dedup when agent_path == workspace | Asserts AGENT.md loaded once under "## Agent Instructions", no "## Project Instructions" |
| `test_launch_agent_success()` | End-to-end success | Asserts agent executes, response success=True, custom instructions used |
| `test_launch_agent_invalid_agent_path()` | Invalid path error | Asserts response success=False, error message about missing path |
| `test_launch_agent_backward_compatible()` | prompt_nano_agent unchanged | Asserts prompt_nano_agent works exactly as before |

### Integration Tests

| Test Function | Verifies | Key Assertions |
|---------------|----------|----------------|
| `test_launch_agent_with_workspace_agent_md()` | Workspace AGENT.md loading | Asserts both agent and project instructions loaded |
| `test_launch_agent_same_path_workspace()` | agent_path == workspace | Asserts AGENT.md loaded once, agent executes successfully |
| `test_launch_agent_relative_path()` | Relative path resolution | Asserts path resolved correctly, agent executes |
| `test_launch_agent_unicode_content()` | Unicode handling | Asserts Unicode characters preserved, no encoding errors |
| `test_prompt_nano_agent_unchanged()` | No regression | Asserts prompt_nano_agent behavior identical to before |

## Files to Create/Modify

### New Files to Create

| File Path | Purpose | Key Content |
|-----------|---------|-------------|
| `apps/nano_agent_mcp_server/src/nano_agent/modules/agent_identity.py` | Agent identity loader | `read_agent_instructions()`, `build_layered_prompt()` functions |
| `apps/nano_agent_mcp_server/tests/test_agent_identity.py` | Unit tests | All unit tests for agent identity loading |

### Existing Files to Modify

| File Path | Changes | Lines Affected |
|-----------|---------|----------------|
| `apps/nano_agent_mcp_server/src/nano_agent/modules/data_types.py` | Add `LaunchAgentRequest` model | Add after line 33 (after `PromptNanoAgentRequest`) |
| `apps/nano_agent_mcp_server/src/nano_agent/modules/nano_agent.py` | Add `instructions_override` param to `_execute_nano_agent_async()` (line ~300) and `_execute_nano_agent()` (line ~431), add `launch_agent()` function after line 650 | Lines 300, 348, 431, 485, 650+ |
| `apps/nano_agent_mcp_server/src/nano_agent/__main__.py` | Import and register `launch_agent` | Add import after line 17, add registration after line 41, update docstring |

## Migration / Backward Compatibility

### Zero-Impact Guarantee

This feature is **100% backward compatible**. Existing users experience no breaking changes:

1. **`prompt_nano_agent()` unchanged**:
   - Zero modifications to existing function
   - Same signature, same behavior, same response schema
   - Existing calls work exactly as before

2. **New tool is additive only**:
   - `launch_agent()` is a separate MCP tool
   - Users who don't call it are unaffected
   - No changes to existing infrastructure

3. **Parameter default is safe**:
   - `instructions_override` defaults to None in both execution functions
   - `prompt_nano_agent()` doesn't pass it (defaults to None → current behavior)
   - `launch_agent()` passes the layered prompt
   - Default behavior preserved

4. **No configuration changes**:
   - No new config files
   - No environment variables
   - No database or state changes

### Migration Path for Users Who Want Agent Identity

Users who want reusable agent personas can opt-in:

1. **Create agent identity directory**:
   ```bash
   mkdir -p ~/Ai_Teams/backend-expert
   ```

2. **Create AGENT.md with identity**:
   ```bash
   cat > ~/Ai_Teams/backend-expert/AGENT.md << 'EOF'
   You are a Python backend expert. Focus on:
   - Clean, testable code with FastAPI
   - Proper database modeling with SQLAlchemy
   - Comprehensive error handling
   - API documentation with OpenAPI
   EOF
   ```

3. **Launch agent with identity**:
   ```python
   await launch_agent(
       "Build a user management API",
       agent_path="~/Ai_Teams/backend-expert",
       workspace="~/projects/my-api"
   )
   ```

### Rollback Plan

If issues arise, the feature can be disabled:

1. **Unregister MCP tool** (comment out 1 line in `__main__.py`):
   ```python
   # mcp.tool()(launch_agent)  # Temporarily disabled
   ```

2. **No data loss or migration needed**:
   - Agent identity files are external (user's directories)
   - No existing configuration modified
   - No database or state changes

## Example Usage

### Example 1: Deploy Backend Expert to New Project

```python
from nano_agent import launch_agent

# Agent identity defined once
# ~/Ai_Teams/backend-expert/AGENT.md:
# "You are a Python backend expert. Focus on FastAPI, SQLAlchemy,
#  clean architecture, and comprehensive testing."

# Deploy to any project
result = await launch_agent(
    "Build a REST API for user management with CRUD operations",
    agent_path="/Users/ahmedmaged/ai_storage/Ai_Teams/backend-expert",
    workspace="/Users/ahmedmaged/projects/my-api",
    model="glm-4.7",
    provider="zai"
)

# Agent executes with backend expertise, applies it to my-api project
# Response: {"success": True, "result": "Built FastAPI application with User model..."}
```

### Example 2: Multi-Agent Collaboration

```python
# Deploy QA agent to test code written by backend agent
# ~/Ai_Teams/qa-engineer/AGENT.md:
# "You are a QA engineer. Always write tests first (TDD), focus on
#  edge cases, and ensure comprehensive test coverage."

backend_result = await launch_agent(
    "Implement user authentication",
    agent_path="/Users/ahmedmaged/ai_storage/Ai_Teams/backend-expert",
    workspace="/Users/ahmedmaged/projects/my-api"
)

qa_result = await launch_agent(
    "Review the authentication implementation and add comprehensive tests",
    agent_path="/Users/ahmedmaged/ai_storage/Ai_Teams/qa-engineer",
    workspace="/Users/ahmedmaged/projects/my-api"
)

# Two different agent identities collaborate on the same project
```

### Example 3: Agent with Project-Specific Rules

```python
# Agent identity + project context
# ~/Ai_Teams/frontend-expert/AGENT.md:
# "You are a React frontend specialist. Focus on components, hooks,
#  state management with Redux, and responsive design."

# /projects/my-app/AGENT.md:
# "This is a TypeScript project. Use strict mode, follow our naming
#  conventions (camelCase for vars, PascalCase for components)."

result = await launch_agent(
    "Create a user profile page with form validation",
    agent_path="/Users/ahmedmaged/ai_storage/Ai_Teams/frontend-expert",
    workspace="/Users/ahmedmaged/projects/my-app"
)

# Agent combines frontend expertise with project-specific TypeScript rules
```

### Example 4: Same Agent, Different Projects

```python
# Reuse same agent identity across multiple projects
projects = [
    "/Users/ahmedmaged/projects/api-1",
    "/Users/ahmedmaged/projects/api-2",
    "/Users/ahmedmaged/projects/api-3"
]

for project in projects:
    result = await launch_agent(
        "Add health check endpoint",
        agent_path="/Users/ahmedmaged/ai_storage/Ai_Teams/backend-expert",
        workspace=project
    )
    print(f"{project}: {result['success']}")

# Same backend expertise applied to all projects
```

---

**End of Spec 10: Agent Identity (launch_agent Tool)**
