# Spec 01: Agent Instructions System

## Overview

The Agent Instructions System is a foundational feature that enables nano-agent to use provider-specific and model-specific instructions, ensuring each LLM receives optimized prompts that match its strengths and capabilities. Currently, all agents use the same `NANO_AGENT_SYSTEM_PROMPT` (defined in `constants.py` line 95), which means Qwen3-Coder receives the same instructions as GPT-5, despite their different prompting requirements. This feature introduces a 4-layer instruction resolution system that automatically loads appropriate instructions based on the selected provider and model, while allowing users to override with custom instructions at both global and workspace levels.

This feature is the highest priority in the v2.0 roadmap because it unblocks multiple downstream features: Execution Templates (US-004) reference instruction sets, Smart Routing (US-005) applies correct instructions per model, and Agent Pipeline (US-006) uses instructions per step. The system is designed to be backward-compatible—existing `prompt_nano_agent()` calls work unchanged with zero configuration, while new calls can leverage the layered instruction system for improved agent quality.

The implementation follows industry standards: Markdown files with optional YAML frontmatter (compatible with Claude Code, GitHub Copilot, AGENTS.md), stored in well-known locations (`<package>/instructions/` for built-ins, `~/.nano-agent/instructions/` for user overrides, and `{workspace}/AGENT.md` for project-specific instructions). Each layer is concatenated with labeled section headers for clear separation and debuggability, making it easy to understand exactly what instructions the agent received.

## Dependencies

### Prerequisites (Must Exist Before Building)
- Python 3.12+ environment with existing nano-agent v1.x codebase
- OpenAI Agent SDK (`agents` package) already installed
- Existing modules: `constants.py`, `data_types.py`, `nano_agent.py`, `provider_config.py`
- PyYAML package (must be added as explicit dependency)

### Unblocked Features (What This Enables)
- **US-004: Execution Templates** — Templates reference instruction sets via frontmatter `instructions:` field
- **US-005: Smart Model Routing** — Applies correct instruction set based on selected model
- **US-006: Agent Pipeline** — Each pipeline step uses appropriate instructions for its model/provider
- **US-009: Agent Memory** — Memory injected as another layer in the instruction stack

## Design Decisions (from PRD Alignment)

These decisions were explicitly discussed and agreed upon during PRD planning. They are **BINDING** and must be followed exactly:

1. **File Format**: Markdown with optional YAML frontmatter (industry standard: Claude Code, GitHub Copilot, AGENTS.md)
2. **Built-in Location**: `<package>/instructions/` directory for provider and model-specific instruction files
3. **User Override Location**: `~/.nano-agent/instructions/` directory for user custom instruction files (override built-ins of same name)
4. **Workspace Instructions**: Auto-detect `{workspace}/AGENT.md` as highest-priority layer (after explicit `instructions` parameter)
5. **Layer Concatenation**: All layers concatenated with labeled section headers (`## Base Instructions`, `## Provider: X`, `## Model: Y`, `## Custom Instructions`, `## Project Instructions`)
6. **Instruction Selection**: Auto-load based on provider/model + manual override via `instructions` parameter
7. **Resolution Order**: explicit `instructions` param > workspace AGENT.md > user ~/.nano-agent/instructions/ > model-specific > provider-level > base NANO_AGENT_SYSTEM_PROMPT
8. **Section Headers**: Each layer wrapped in `## Section Header` for clear separation and debuggability
9. **Backward Compatibility**: `instructions=None` → auto-load (enhanced behavior). Existing calls work unchanged.
10. **YAML Frontmatter**: Optional metadata fields: `compatible_models` (list), `version` (string), `author` (string), `description` (string)
11. **Graceful Degradation**: Missing instruction files at any layer are skipped (no errors)
12. **File Naming**: Provider files use lowercase provider name (`ollama.md`, `openai.md`), model files use model identifier with slashes replaced by dashes (`glm-4.7.md`, `qwen3-coder-30b.md`)

## Architecture

### Instruction Selection

The `instructions` parameter is a **file name** (without `.md` extension), not inline instruction text. Example: `instructions="tdd"` loads `tdd.md` from user or built-in directory. To pass inline instructions, users should create a file first.

### Instruction Resolution Order

The instruction system uses a 4-layer resolution with clear priority ordering:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. EXPLICIT INSTRUCTIONS PARAMETER (Highest Priority)           │
│    User passes instructions="my-custom" to prompt_nano_agent()  │
├─────────────────────────────────────────────────────────────────┤
│ 2. WORKSPACE AGENT.md                                           │
│    Auto-detect {workspace}/AGENT.md if it exists                │
├─────────────────────────────────────────────────────────────────┤
│ 3. USER CUSTOM INSTRUCTIONS                                     │
│    ~/.nano-agent/instructions/{model}.md or {provider}.md       │
├─────────────────────────────────────────────────────────────────┤
│ 4. MODEL-SPECIFIC BUILT-IN                                      │
│    <package>/instructions/{model}.md (e.g., glm-4.7.md)         │
├─────────────────────────────────────────────────────────────────┤
│ 5. PROVIDER-LEVEL BUILT-IN                                      │
│    <package>/instructions/{provider}.md (e.g., ollama.md)       │
├─────────────────────────────────────────────────────────────────┤
│ 6. BASE INSTRUCTIONS (Lowest Priority - Always Included)        │
│    NANO_AGENT_SYSTEM_PROMPT from constants.py                   │
└─────────────────────────────────────────────────────────────────┘
```

**Final System Prompt Assembly** (base first, custom last):
```
## Base Instructions
{NANO_AGENT_SYSTEM_PROMPT content}

## Provider: ollama
{Provider-specific instructions from ollama.md}

## Model: qwen3-coder:30b
{Model-specific instructions from qwen3-coder-30b.md}

## Custom Instructions
{User custom instructions from ~/.nano-agent/instructions/}

## Project Instructions
{Workspace AGENT.md content}

Workspace directory: {workspace_path}
```

### File Locations

| Location | Purpose | Example Files | Priority |
|----------|---------|---------------|----------|
| `<package>/instructions/` | Built-in provider/model instructions | `ollama.md`, `glm-4.7.md`, `qwen3-coder-30b.md` | Low (4-5) |
| `~/.nano-agent/instructions/` | User custom instructions (override built-ins) | `my-custom.md`, `glm-4.7.md` (overrides built-in) | Medium (3) |
| `{workspace}/AGENT.md` | Project-specific instructions | `AGENT.md` in any workspace | High (2) |
| Explicit parameter | Manual override via `instructions="name"` | Any file in user or built-in locations | Highest (1) |

**Path Resolution**:
- Built-in: `apps/nano_agent_mcp_server/src/nano_agent/instructions/`
- User: `Path.home() / ".nano-agent" / "instructions"`
- Workspace: `Path(workspace) / "AGENT.md"`

### Instruction File Format

Instruction files use Markdown with optional YAML frontmatter:

```markdown
---
compatible_models:
  - qwen3-coder:30b
  - qwen3-coder:20b
version: "1.0"
author: "nano-agent team"
description: "Optimized instructions for Qwen3 Coder models"
---

You are Qwen3-Coder, a specialized coding model. Focus on:

1. **Code Quality**: Write clean, well-documented code with type hints
2. **Testing**: Always include test cases when implementing new features
3. **Python Best Practices**: Use context managers, f-strings, and dataclasses

When editing files, prefer surgical edits over complete rewrites.
```

**YAML Frontmatter Fields** (all optional):
- `compatible_models`: List of model identifiers this instruction applies to (informational only in v2.0; the loader does NOT filter based on this field. Future versions may use it for validation. Including it helps with discovery and documentation.)
- `version`: Instruction version string
- `author`: Author name or identifier
- `description`: Human-readable description of the instruction set

**Body Content**: Plain Markdown that will be inserted into the system prompt under the appropriate section header.

### Resolution Priority (File Selection)

When loading provider/model instructions, files are searched in this order:
1. User directory (`~/.nano-agent/instructions/`) — checked FIRST
2. Built-in directory (`<package>/instructions/`) — fallback

If a file exists in both, the USER version wins (override behavior).

### Concatenation Order (Prompt Assembly)

The final system prompt is assembled top-to-bottom:
1. ## Base Instructions (always first)
2. ## Provider: {provider}
3. ## Model: {model}
4. ## Custom Instructions (from explicit parameter)
5. ## Project Instructions (from workspace AGENT.md)
6. Workspace directory: {path}

Note: Resolution priority determines WHICH file loads; concatenation order determines WHERE it appears.

### System Prompt Composition

The final system prompt is assembled in `nano_agent.py` where instructions are currently built:

**Current Code** (async version, line 348-349):
```python
# Build instructions with workspace context
instructions = NANO_AGENT_SYSTEM_PROMPT + f"\n\nWorkspace directory: {workspace_path}\n"
```

**Current Code** (sync version, line 485-486):
```python
# Build instructions with workspace context
instructions = NANO_AGENT_SYSTEM_PROMPT + f"\n\nWorkspace directory: {workspace_path}\n"
```

**New Code** (after implementation):
```python
# Build instructions with 4-layer resolution
instruction_result = InstructionLoader.load_instructions(
    provider=request.provider,
    model=request.model,
    workspace=request.workspace,
    custom_instructions=request.instructions  # From new parameter
)
instructions = instruction_result.prompt
instructions += f"\n\nWorkspace directory: {workspace_path}\n"
```

**Assembly Process**:
1. Start with `## Base Instructions\n{NANO_AGENT_SYSTEM_PROMPT}`
2. Append provider layer if found: `\n\n## Provider: {provider}\n{provider_instructions}`
3. Append model layer if found: `\n\n## Model: {model}\n{model_instructions}`
4. Append user custom layer if found: `\n\n## Custom Instructions\n{custom_instructions}`
5. Append workspace layer if found: `\n\n## Project Instructions\n{workspace_instructions}`
6. Append workspace directory: `\n\nWorkspace directory: {workspace_path}\n`

**Empty Layer Rule**: If an instruction file exists but has an empty body (after frontmatter extraction), the layer is SKIPPED — no section header is added. This keeps prompts clean and avoids confusing empty sections.

## Implementation Phases

### Phase A: Core Instruction Loader
**Objective**: Create the instruction loading module with 4-layer resolution logic

#### Tasks (Human-Level)
1. Create new `instructions.py` module with `InstructionLoader` class
2. Implement file path resolution for built-in, user, and workspace locations
3. Implement Markdown + YAML frontmatter parsing
4. Implement 4-layer resolution with section header concatenation
5. Add comprehensive unit tests for all loading scenarios

#### Sub-Tasks (Nano-Agent Delegation Ready)

##### Sub-Task A0: Add PyYAML dependency
- **File to modify**: `apps/nano_agent_mcp_server/pyproject.toml`
- **What to implement**:
  - Add `pyyaml>=6.0` to the `dependencies` array (line 10)
  - This is required for parsing YAML frontmatter in instruction files
- **Acceptance criteria**:
  - `pyyaml>=6.0` appears in dependencies list
  - Package installs successfully with `uv sync` or `pip install`
- **Example input → output**:
  - Input: `dependencies = ["mcp[cli]>=1.12.4", ...]`
  - Output: `dependencies = ["mcp[cli]>=1.12.4", ..., "pyyaml>=6.0"]`

##### Sub-Task A1: Create instructions.py module skeleton
- **File to create**: `apps/nano_agent_mcp_server/src/nano_agent/modules/instructions.py`
- **What to implement**:
  - Module docstring explaining the 4-layer instruction system
  - Import statements: `pathlib.Path`, `logging`, `re`, `yaml` (add PyYAML if needed)
  - Define `InstructionLoader` class with empty methods
  - Define constants for instruction directory paths
- **Existing patterns to follow**:
  - Follow module structure from `constants.py` (lines 1-15: docstring, imports, constants)
  - Use `logger = logging.getLogger(__name__)` pattern from `provider_config.py` line 18
- **Acceptance criteria**:
  - Module imports without errors
  - `InstructionLoader` class is defined
  - Constants `BUILT_IN_INSTRUCTIONS_DIR`, `USER_INSTRUCTIONS_DIR` are defined
- **Example input → output**:
  - Input: `from nano_agent.modules.instructions import InstructionLoader`
  - Output: Module imports successfully, `InstructionLoader` class available

##### Sub-Task A2: Implement path resolution methods
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/instructions.py`
- **What to implement**:
  - `_get_built_in_instructions_dir()` → returns `Path(__file__).parent.parent / "instructions"`
  - `_get_user_instructions_dir()` → returns `Path.home() / ".nano-agent" / "instructions"`
  - `_get_workspace_agent_md(workspace: str | None) → Path | None`
  - `_sanitize_filename(name: str) → str` (replace `/` with `-`, lowercase, remove invalid chars)
- **Existing patterns to follow**:
  - Follow `set_workspace()` pattern from `nano_agent_tools.py` for workspace path handling
  - Use `Path.home()` pattern from constants (not currently used, but standard library)
- **Acceptance criteria**:
  - Built-in path resolves to package instructions directory
  - User path resolves to `~/.nano-agent/instructions/`
  - Workspace path returns `None` if workspace is `None` or empty
  - Filename sanitization: `"qwen3-coder:30b"` → `"qwen3-coder-30b"`, `"GLM-4.7"` → `"glm-4.7"`
- **Example input → output**:
  - Input: `_sanitize_filename("qwen3-coder:30b")`
  - Output: `"qwen3-coder-30b"`
  - Input: `_sanitize_filename("GLM-4.7")`
  - Output: `"glm-4.7"`

##### Sub-Task A3: Implement instruction file reading with YAML frontmatter parsing
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/instructions.py`
- **What to implement**:
  - `_read_instruction_file(file_path: Path) → dict | None`
  - Parse YAML frontmatter between `---` delimiters
  - Extract metadata (compatible_models, version, author, description)
  - Extract body content (Markdown after frontmatter)
  - Return `{"metadata": dict, "content": str}` or `None` if file not found
- **Existing patterns to follow**:
  - Follow file reading pattern from `read_file()` in `nano_agent_tools.py` (lines 20-50)
  - Use `Path.exists()` and `Path.read_text()` for file operations
- **Acceptance criteria**:
  - Returns `None` if file doesn't exist (graceful degradation)
  - Correctly parses YAML frontmatter with `---` delimiters
  - Handles files without frontmatter (entire file is content)
  - Handles files with only frontmatter (content is empty string)
  - Logs debug messages when loading files
- **Example input → output**:
  - Input: File at `/test.md` with content `"---\nversion: 1.0\n---\n\nInstructions here"`
  - Output: `{"metadata": {"version": "1.0"}, "content": "\nInstructions here"}`
  - Input: Non-existent file
  - Output: `None`

##### Sub-Task A4: Implement 4-layer resolution logic
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/instructions.py`
- **What to implement**:
  - Define `InstructionResult` dataclass with `prompt: str` and `layers: list[str]` fields
  - `load_instructions(provider: str, model: str, workspace: str | None, custom_instructions: str | None) → InstructionResult`
  - Resolution order: custom param > workspace AGENT.md > user custom > model-specific > provider-level > base
  - Each layer wrapped in section header: `## Layer Name\n{content}`
  - Concatenate all found layers with base prompt always first
  - Track which layers were loaded in the `layers` list (e.g., `["base", "provider:ollama", "model:qwen3-coder-30b", "workspace"]`)
- **Existing patterns to follow**:
  - Follow string concatenation pattern from `nano_agent.py` line 348
  - Use `NANO_AGENT_SYSTEM_PROMPT` from `constants.py` as base
- **Acceptance criteria**:
  - Base instructions always included first
  - Provider layer loaded if `{provider}.md` exists in built-in or user dir
  - Model layer loaded if `{sanitized_model}.md` exists in built-in or user dir
  - Custom layer loaded if `custom_instructions` parameter provided
  - Workspace layer loaded if `{workspace}/AGENT.md` exists
  - Each layer separated by `\n\n## Section Header\n`
  - Returns `InstructionResult` with both assembled prompt and list of loaded layers
- **Example input → output**:
  - Input: `provider="ollama"`, `model="qwen3-coder:30b"`, `workspace="/tmp/project"`, `custom_instructions=None`
  - Output: `InstructionResult(prompt="## Base Instructions\n{NANO_AGENT_SYSTEM_PROMPT}\n\n## Provider: ollama\n{ollama.md content}\n\n## Model: qwen3-coder:30b\n{qwen3-coder-30b.md content}\n\n## Project Instructions\n{AGENT.md content}", layers=["base", "provider:ollama", "model:qwen3-coder-30b", "workspace"])`
  - Input: All layers missing except base
  - Output: `InstructionResult(prompt="## Base Instructions\n{NANO_AGENT_SYSTEM_PROMPT}", layers=["base"])`

##### Sub-Task A5: Create comprehensive unit tests
- **File to create**: `apps/nano_agent_mcp_server/tests/test_instructions.py`
- **What to implement**:
  - `test_sanitize_filename()` → verify filename sanitization
  - `test_read_instruction_file_with_frontmatter()` → verify YAML parsing
  - `test_read_instruction_file_without_frontmatter()` → verify plain Markdown handling
  - `test_read_instruction_file_not_found()` → verify graceful degradation
  - `test_load_instructions_base_only()` → verify base prompt always included
  - `test_load_instructions_with_provider_layer()` → verify provider layer loading
  - `test_load_instructions_with_model_layer()` → verify model layer loading
  - `test_load_instructions_with_custom_param()` → verify custom parameter override
  - `test_load_instructions_with_workspace_agent_md()` → verify workspace detection
  - `test_load_instructions_full_stack()` → verify all layers combined
  - `test_user_overrides_built_in()` → verify user instructions override built-ins
- **Existing patterns to follow**:
  - Follow test structure from existing tests (if any exist in project)
  - Use `pytest` and `tmp_path` fixture for file system tests
- **Acceptance criteria**:
  - All tests pass
  - Test coverage >90% for instructions module
  - Edge cases covered (empty files, malformed YAML, missing files)

### Phase B: Wire Into Agent Execution
**Objective**: Integrate instruction loader into the agent creation flow

#### Tasks (Human-Level)
1. Add `instructions` parameter to `PromptNanoAgentRequest` model
2. Update `prompt_nano_agent()` function signature to accept `instructions` parameter
3. Replace hardcoded instruction building with `InstructionLoader.load_instructions()`
4. Update both sync and async execution paths
5. Add integration tests

#### Sub-Tasks (Nano-Agent Delegation Ready)

##### Sub-Task B1: Extend PromptNanoAgentRequest model
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/data_types.py`
- **What to implement**:
  - Add `instructions: Optional[str] = Field(default=None, description="Custom instruction set name or path")` to `PromptNanoAgentRequest` class (after line 32)
  - Update docstring to document the new parameter
- **Existing patterns to follow**:
  - Follow existing field pattern from `workspace` field (lines 28-32)
  - Use `Optional[str]` with `Field(default=None)` for optional parameters
- **Acceptance criteria**:
  - `PromptNanoAgentRequest` accepts `instructions` parameter
  - Pydantic validation works correctly
  - Default value is `None`
- **Example input → output**:
  - Input: `PromptNanoAgentRequest(agentic_prompt="test", instructions="my-custom")`
  - Output: Valid model instance with `instructions="my-custom"`

##### Sub-Task B2: Update prompt_nano_agent function signature
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/nano_agent.py`
- **What to implement**:
  - Add `instructions: Optional[str] = None` parameter to `prompt_nano_agent()` function (after `workspace` parameter, line 576)
  - Add parameter to docstring with description and examples
  - Pass `instructions` to `PromptNanoAgentRequest` constructor
- **Existing patterns to follow**:
  - Follow existing parameter pattern from `workspace` parameter
  - Update docstring to match existing parameter documentation style
- **Acceptance criteria**:
  - Function signature includes `instructions` parameter
  - Docstring documents the parameter with examples
  - Parameter is passed to request constructor
- **Example input → output**:
  - Input: `await prompt_nano_agent("Write code", instructions="python-expert")`
  - Output: Agent executes with "python-expert" instruction set loaded

##### Sub-Task B2.5: Verify MCP tool registration
- **File to verify**: `apps/nano_agent_mcp_server/src/nano_agent/__main__.py`
- **What to verify**:
  - The `prompt_nano_agent` function is registered as an MCP tool via `mcp.tool()(prompt_nano_agent)` (line 36)
  - Since the function is imported directly and decorated, updating its signature in `nano_agent.py` (Sub-Task B2) automatically updates the MCP tool's exposed signature
  - No additional changes needed to `__main__.py`
- **Acceptance criteria**:
  - Verification complete: MCP tool will expose the new `instructions` parameter
  - No code changes required in `__main__.py`

##### Sub-Task B3: Replace instruction building in _execute_nano_agent_async
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/nano_agent.py`
- **What to implement**:
  - Import `InstructionLoader` from `.instructions` (line ~23)
  - Replace lines 348-349 with call to `InstructionLoader.load_instructions()`
  - Pass `request.provider`, `request.model`, `request.workspace`, `request.instructions`
  - Store result in `instruction_result` variable
  - Extract `instruction_result.prompt` to `instructions` variable
  - Extract `instruction_result.layers` and add to response metadata
- **Existing patterns to follow**:
  - Follow import pattern from existing imports (lines 11-27)
  - Maintain existing variable naming (`instructions`)
- **Acceptance criteria**:
  - Old hardcoded instruction building removed
  - New `InstructionLoader.load_instructions()` called with correct parameters
  - `instructions` variable contains layered system prompt
  - Response metadata includes `instruction_layers` list
- **Example input → output**:
  - Input: `request.provider="ollama"`, `request.model="qwen3-coder:30b"`, `request.workspace="/tmp/test"`, `request.instructions=None`
  - Output: `instructions` variable contains base + provider + model + workspace layers, metadata includes `{"instruction_layers": ["base", "provider:ollama", "model:qwen3-coder-30b", "workspace"]}`

##### Sub-Task B4: Replace instruction building in _execute_nano_agent (sync version)
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/nano_agent.py`
- **What to implement**:
  - Same changes as Sub-Task B3 but for sync version at line 485-486
  - Ensure both sync and async paths use same instruction loading logic
  - Extract `instruction_result.layers` and add to response metadata
- **Existing patterns to follow**:
  - Mirror changes from async version
  - Keep both implementations identical for instruction loading
- **Acceptance criteria**:
  - Sync version uses `InstructionLoader.load_instructions()`
  - Behavior matches async version
  - Response metadata includes `instruction_layers` list

##### Sub-Task B5: Add integration tests
- **File to create**: `apps/nano_agent_mcp_server/tests/test_instructions_integration.py`
- **What to implement**:
  - `test_prompt_nano_agent_with_custom_instructions()` → verify custom parameter works
  - `test_prompt_nano_agent_with_workspace_agent_md()` → verify workspace detection
  - `test_prompt_nano_agent_backward_compatible()` → verify existing calls work unchanged
  - `test_prompt_nano_agent_instruction_layers_in_metadata()` → verify layers recorded in response
- **Existing patterns to follow**:
  - Follow integration test patterns if they exist in project
  - Use `pytest` and mock file system for testing
- **Acceptance criteria**:
  - All integration tests pass
  - Backward compatibility verified (existing calls work)

### Phase C: Built-In Instruction Files
**Objective**: Create default instruction .md files for all providers and key models

#### Tasks (Human-Level)
1. Create `instructions/` directory in package
2. Write provider-level instruction files for all 5 providers
3. Write model-level instruction files for commonly used models
4. Ensure all files follow the Markdown + YAML frontmatter format

#### Sub-Tasks (Nano-Agent Delegation Ready)

##### Sub-Task C1: Create instructions directory
- **Directory to create**: `apps/nano_agent_mcp_server/src/nano_agent/instructions/`
- **What to implement**:
  - Create directory structure
  - Add `README.md` explaining the instruction file format
  - Ensure directory is included in package data via `pyproject.toml` (verify correct mechanism for uv_build)
  - Note: Do NOT create `__init__.py` — this directory holds Markdown data files, not Python code
- **Existing patterns to follow**:
  - Follow directory structure from `modules/` directory
- **Acceptance criteria**:
  - Directory exists at correct path
  - `README.md` documents instruction file format
  - No `__init__.py` file (not a Python package)
  - Directory included in package distribution

##### Sub-Task C2: Create provider instruction files
- **Files to create**:
  - `apps/nano_agent_mcp_server/src/nano_agent/instructions/openai.md`
  - `apps/nano_agent_mcp_server/src/nano_agent/instructions/anthropic.md`
  - `apps/nano_agent_mcp_server/src/nano_agent/instructions/ollama.md`
  - `apps/nano_agent_mcp_server/src/nano_agent/instructions/lmstudio.md`
  - `apps/nano_agent_mcp_server/src/nano_agent/instructions/zai.md`
- **What to implement**:
  - Each file contains provider-specific guidance
  - Include YAML frontmatter with `compatible_models`, `version`, `author`, `description`
  - Body content optimized for the provider's model characteristics
- **Content guidelines**:
  - **OpenAI**: Focus on JSON tool output format, function calling best practices
  - **Anthropic**: Emphasize XML thinking format, Claude-specific capabilities
  - **Ollama**: Note local model constraints, response latency considerations
  - **LM Studio**: Local model serving via HTTP API (OpenAI-compatible). Note: models run on user's hardware with limited context windows. Emphasize: concise outputs, avoid unnecessary explanations, focus on code generation. Mention that LM Studio supports multiple models loaded simultaneously.
  - **Z.ai**: GLM model specifics, Chinese/English bilingual support
- **Acceptance criteria**:
  - All 5 provider files created
  - Each file has valid YAML frontmatter
  - Content is provider-specific and actionable

##### Sub-Task C3: Create model instruction files
- **Files to create**:
  - `apps/nano_agent_mcp_server/src/nano_agent/instructions/glm-4.7.md`
  - `apps/nano_agent_mcp_server/src/nano_agent/instructions/qwen3-coder-30b.md`
  - `apps/nano_agent_mcp_server/src/nano_agent/instructions/gpt-5-mini.md`
  - `apps/nano_agent_mcp_server/src/nano_agent/instructions/claude-opus-4-20250514.md`
- **What to implement**:
  - Model-specific optimization guidance
  - Include YAML frontmatter with `compatible_models` listing specific model versions
  - Body content with model-specific prompting strategies
- **Content guidelines**:
  - **GLM-4.7**: Strong reasoning, bilingual, structured output
  - **Qwen3-Coder**: Code generation focus, Python/JavaScript optimization
  - **GPT-5-mini**: Fast execution, simple tasks, cost efficiency
  - **Claude Opus 4**: Complex reasoning, long context, careful analysis
- **Acceptance criteria**:
  - All 4 model files created
  - Each file has valid YAML frontmatter
  - Content is model-specific and actionable
- **Note**: These 4 model files cover the most commonly used models. Additional model instruction files can be added incrementally — the loader automatically picks up any `.md` file matching the sanitized model name.

### Phase D: Workspace AGENT.md Detection
**Objective**: Auto-detect and load project-level instructions from workspace

#### Tasks (Human-Level)
1. Implement workspace AGENT.md file detection
2. Add logging when workspace instructions are loaded
3. Handle edge cases (file exists but unreadable, directory permissions)
4. Add tests for workspace detection

#### Sub-Tasks (Nano-Agent Delegation Ready)

##### Sub-Task D1: Implement workspace AGENT.md detection
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/instructions.py`
- **What to implement**:
  - In `_get_workspace_agent_md()` method, check if workspace path is provided
  - Construct path to `{workspace}/AGENT.md`
  - Return `Path` object if file exists, `None` otherwise
  - Add debug logging when file is found or not found
- **Existing patterns to follow**:
  - Follow file existence check pattern from `read_file()` in `nano_agent_tools.py`
  - Use `Path.exists()` for existence check
- **Acceptance criteria**:
  - Returns `None` if workspace is `None` or empty string
  - Returns `None` if AGENT.md doesn't exist in workspace
  - Returns `Path` to AGENT.md if it exists
  - Logs appropriate debug messages
- **Example input → output**:
  - Input: `workspace="/tmp/project"`, AGENT.md exists
  - Output: `Path("/tmp/project/AGENT.md")`, log message "Found workspace AGENT.md"
  - Input: `workspace=None`
  - Output: `None`, no log message

##### Sub-Task D2: Add workspace layer to load_instructions
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/instructions.py`
- **What to implement**:
  - In `load_instructions()` method, call `_get_workspace_agent_md()`
  - If path returned, read file using `_read_instruction_file()`
  - If content exists, append `## Project Instructions\n{content}` to result
  - Log info message when workspace instructions are loaded
- **Existing patterns to follow**:
  - Follow layer concatenation pattern from other layers
  - Use same section header format: `## Project Instructions`
- **Acceptance criteria**:
  - Workspace layer loaded after custom layer
  - Section header is `## Project Instructions`
  - Info logged when workspace instructions found
  - Gracefully handles missing file (no error)
- **Example input → output**:
  - Input: `workspace="/tmp/project"`, AGENT.md exists with content "Project-specific rules"
  - Output: System prompt includes `\n\n## Project Instructions\nProject-specific rules`

##### Sub-Task D3: Add tests for workspace detection
- **File to modify**: `apps/nano_agent_mcp_server/tests/test_instructions.py`
- **What to implement**:
  - `test_workspace_agent_md_found()` → verify detection when file exists
  - `test_workspace_agent_md_not_found()` → verify graceful handling when missing
  - `test_workspace_agent_md_none_workspace()` → verify handling when workspace is None
  - `test_workspace_agent_md_unreadable()` → verify handling when file exists but unreadable
- **Existing patterns to follow**:
  - Use `tmp_path` fixture to create temporary workspace directories
  - Use `pytest.raises` for error handling tests
- **Acceptance criteria**:
  - All workspace tests pass
  - Edge cases covered (None workspace, missing file, unreadable file)

## Acceptance Criteria

Full checklist from PRD US-001, expanded with technical details:

- [ ] **4-layer instruction system implemented**: Base prompt → provider `.md` → model `.md` → user custom `.md` + workspace AGENT.md
- [ ] **Each layer wrapped in labeled section headers**: `## Base Instructions`, `## Provider: {provider}`, `## Model: {model}`, `## Custom Instructions`, `## Project Instructions`
- [ ] **Workspace-level AGENT.md auto-detected**: Automatically loaded from `{workspace}/AGENT.md` if it exists
- [ ] **Instruction files use Markdown with optional YAML frontmatter**: Compatible with industry standard (Claude Code, GitHub Copilot)
- [ ] **Built-in instructions shipped in `<package>/instructions/`**: Provider files (`ollama.md`, `openai.md`, etc.) and model files (`glm-4.7.md`, `qwen3-coder-30b.md`, etc.)
- [ ] **User instructions in `~/.nano-agent/instructions/` override built-ins**: Same filename overrides built-in file
- [ ] **User can pass `instructions="my-custom"` parameter**: Loads named instruction set from user or built-in directory
- [ ] **Resolution order implemented correctly**: explicit param > workspace AGENT.md > user custom > model-specific > provider-level > base prompt
- [ ] **All existing tests pass with no regressions**: Backward compatibility maintained
- [ ] **New tests verify instruction loading**: Unit tests for file reading, YAML parsing, layer resolution
- [ ] **New tests verify layering and fallback**: Tests for missing files, override behavior, graceful degradation
- [ ] **New tests verify workspace detection**: Tests for AGENT.md auto-detection and loading
- [ ] **PyYAML dependency added to pyproject.toml**: `pyyaml>=6.0` in dependencies array
- [ ] **Documentation updated**: Docstrings, README, and examples reflect new functionality

## Scenarios

### Happy Path

#### Scenario 1: Agent with provider instructions
**Input**:
```python
await prompt_nano_agent(
    "Write a FastAPI endpoint",
    provider="ollama",
    model="qwen3-coder:30b"
)
```

**Expected Behavior**:
1. `InstructionLoader.load_instructions()` called with `provider="ollama"`, `model="qwen3-coder:30b"`
2. Base instructions loaded from `NANO_AGENT_SYSTEM_PROMPT`
3. Provider instructions loaded from `<package>/instructions/ollama.md`
4. Model instructions loaded from `<package>/instructions/qwen3-coder-30b.md`
5. No custom instructions (parameter is `None`)
6. No workspace instructions (workspace not specified or AGENT.md doesn't exist)
7. Final system prompt:
   ```
   ## Base Instructions
   {NANO_AGENT_SYSTEM_PROMPT content}
   
   ## Provider: ollama
   {ollama.md content about local models, latency, etc.}
   
   ## Model: qwen3-coder:30b
   {qwen3-coder-30b.md content about code generation, Python optimization}
   ```
8. Agent executes with optimized instructions for Ollama Qwen3-Coder

#### Scenario 2: Agent with model-specific instructions
**Input**:
```python
await prompt_nano_agent(
    "Analyze this codebase",
    provider="zai",
    model="glm-4.7"
)
```

**Expected Behavior**:
1. Base instructions loaded
2. Provider instructions loaded from `<package>/instructions/zai.md`
3. Model instructions loaded from `<package>/instructions/glm-4.7.md`
4. Final system prompt includes all three layers
5. Agent executes with GLM-4.7 optimized instructions (bilingual support, strong reasoning)

#### Scenario 3: Agent with user custom instructions
**Input**:
```python
# User created ~/.nano-agent/instructions/python-expert.md
await prompt_nano_agent(
    "Refactor this Python code",
    instructions="python-expert"
)
```

**Expected Behavior**:
1. Base instructions loaded
2. Provider/model layers loaded based on selected provider/model
3. Custom instructions loaded from `~/.nano-agent/instructions/python-expert.md`
4. Final system prompt includes `## Custom Instructions` layer with user's Python expert guidelines
5. Agent executes with user's custom Python optimization rules

#### Scenario 4: Agent with workspace AGENT.md
**Input**:
```python
# /tmp/myproject/AGENT.md exists with project-specific rules
await prompt_nano_agent(
    "Add a new feature",
    workspace="/tmp/myproject"
)
```

**Expected Behavior**:
1. Base instructions loaded
2. Provider/model layers loaded
3. Workspace AGENT.md detected and loaded
4. Final system prompt includes `## Project Instructions` layer with project-specific rules
5. Agent executes with awareness of project conventions

#### Scenario 5: All layers combined
**Input**:
```python
# All conditions present:
# - Built-in provider/model instructions exist
# - User has ~/.nano-agent/instructions/custom-override.md
# - Workspace has AGENT.md
# - User passes instructions="custom-override"
await prompt_nano_agent(
    "Complex multi-file task",
    provider="ollama",
    model="qwen3-coder:30b",
    workspace="/tmp/project",
    instructions="custom-override"
)
```

**Expected Behavior**:
1. Base instructions loaded (always first)
2. Provider layer: `## Provider: ollama`
3. Model layer: `## Model: qwen3-coder:30b`
4. Custom layer: `## Custom Instructions` (from explicit parameter, highest priority)
5. Workspace layer: `## Project Instructions` (from AGENT.md)
6. Final system prompt contains all 5 layers in correct order
7. Agent executes with comprehensive, layered instructions

### Negative Cases

#### Scenario 1: No instruction files exist (graceful fallback to base prompt)
**Input**:
```python
# No built-in instructions, no user instructions, no workspace AGENT.md
await prompt_nano_agent(
    "Simple task",
    provider="ollama",
    model="unknown-model"
)
```

**Expected Behavior**:
1. `InstructionLoader.load_instructions()` attempts to load all layers
2. Provider file `ollama.md` not found → skip layer (no error)
3. Model file `unknown-model.md` not found → skip layer (no error)
4. Custom parameter is `None` → skip layer
5. Workspace AGENT.md not found → skip layer
6. Only base instructions returned: `## Base Instructions\n{NANO_AGENT_SYSTEM_PROMPT}`
7. Agent executes normally with base prompt only
8. No errors thrown, graceful degradation

#### Scenario 2: Malformed YAML frontmatter
**Input**:
```markdown
# File: ~/.nano-agent/instructions/bad-yaml.md
---
version: 1.0
compatible_models:
  - model1
  bad yaml here [[[
---
Instructions here
```

**Expected Behavior**:
1. `_read_instruction_file()` attempts to parse YAML frontmatter
2. YAML parsing fails (invalid syntax)
3. Error logged: "Failed to parse YAML frontmatter in {file_path}: {error}"
4. File treated as having no frontmatter (entire content is body)
5. Instructions still loaded from body content
6. Agent executes with instructions (metadata is empty dict)
7. No crash, graceful error handling

#### Scenario 3: Instruction file not found for specified name
**Input**:
```python
await prompt_nano_agent(
    "Task",
    instructions="non-existent-instruction-set"
)
```

**Expected Behavior**:
1. `InstructionLoader.load_instructions()` looks for `non-existent-instruction-set.md`
2. Searches user directory: `~/.nano-agent/instructions/non-existent-instruction-set.md` → not found
3. Searches built-in directory: `<package>/instructions/non-existent-instruction-set.md` → not found
4. Warning logged: "Custom instruction set 'non-existent-instruction-set' not found, skipping"
5. Other layers loaded normally (base, provider, model, workspace)
6. Agent executes without custom layer
7. Response includes success, no error about missing instructions

#### Scenario 4: Empty instruction file
**Input**:
```markdown
# File: ~/.nano-agent/instructions/empty.md
---
version: 1.0
---
```

**Expected Behavior**:
1. `_read_instruction_file()` reads file successfully
2. YAML frontmatter parsed: `{"version": "1.0"}`
3. Body content is empty string
4. Layer is SKIPPED (no section header added) — per Empty Layer Rule
5. Agent executes normally (layer not included in prompt)
6. No error, graceful handling

### Edge Cases

#### Scenario 1: Very large instruction file (>10KB)
**Input**:
```python
# File: ~/.nano-agent/instructions/huge.md (15KB of text)
await prompt_nano_agent(
    "Task",
    instructions="huge"
)
```

**Expected Behavior**:
1. File read successfully (no size limit enforced)
2. Entire content included in system prompt
3. Warning logged: "Large instruction file 'huge.md' (15KB), may impact token usage"
4. Agent executes with large instruction set
5. Token tracking reflects increased input tokens
6. No crash or truncation

#### Scenario 2: Instruction file with only YAML frontmatter, no body
**Input**:
```markdown
# File: ~/.nano-agent/instructions/metadata-only.md
---
version: 1.0
author: "test"
compatible_models:
  - gpt-5-mini
---
```

**Expected Behavior**:
1. File parsed successfully
2. Metadata extracted: `{"version": "1.0", "author": "test", "compatible_models": ["gpt-5-mini"]}`
3. Body content is empty string
4. Layer is SKIPPED (no section header added) — per Empty Layer Rule
5. Agent executes normally
6. No error

#### Scenario 3: Multiple AGENT.md files in workspace subdirectories
**Input**:
```python
# File structure:
# /tmp/project/
#   AGENT.md (root level)
#   subdir/
#     AGENT.md (subdirectory)
await prompt_nano_agent(
    "Task",
    workspace="/tmp/project"
)
```

**Expected Behavior**:
1. Only root-level AGENT.md loaded: `/tmp/project/AGENT.md`
2. Subdirectory AGENT.md ignored (not in workspace root)
3. Info logged: "Found workspace AGENT.md at /tmp/project/AGENT.md"
4. Agent executes with root-level project instructions
5. No confusion or multiple loading

#### Scenario 4: Unicode/special characters in instruction files
**Input**:
```markdown
# File: ~/.nano-agent/instructions/unicode.md
---
version: "1.0"
---
# Instructions with Unicode

You should handle: 中文, 日本語, 한국어, emoji 🚀, and special chars: <>&"''
```

**Expected Behavior**:
1. File read with UTF-8 encoding (default)
2. Unicode characters preserved correctly
3. System prompt includes all Unicode characters
4. Agent receives instructions with proper encoding
5. No encoding errors or character corruption

#### Scenario 5: Circular instruction references (if applicable)
**Input**:
```python
# Note: This scenario is for future-proofing if instruction references are added
# Current implementation doesn't support references, so this is N/A
```

**Expected Behavior**:
1. N/A - current implementation doesn't support instruction references
2. If added in future, implement cycle detection to prevent infinite loops

## Test Plan

### Unit Tests (test_instructions.py)

| Test Function | Verifies | Key Assertions |
|---------------|----------|----------------|
| `test_sanitize_filename()` | Filename sanitization | Asserts `/` replaced with `-`, lowercase applied, special chars removed |
| `test_read_instruction_file_with_frontmatter()` | YAML parsing | Asserts metadata extracted, content extracted, both correct |
| `test_read_instruction_file_without_frontmatter()` | Plain Markdown | Asserts entire file is content, metadata is empty dict |
| `test_read_instruction_file_not_found()` | Graceful degradation | Asserts returns `None`, no error thrown |
| `test_read_instruction_file_empty()` | Empty file handling | Asserts returns empty content, no crash |
| `test_read_instruction_file_malformed_yaml()` | YAML error handling | Asserts logs error, treats entire file as content |
| `test_load_instructions_base_only()` | Base prompt always included | Asserts result.prompt starts with "## Base Instructions", contains NANO_AGENT_SYSTEM_PROMPT, result.layers == ["base"] |
| `test_load_instructions_with_provider_layer()` | Provider layer loading | Asserts includes "## Provider: ollama", provider content present, "provider:ollama" in layers list |
| `test_load_instructions_with_model_layer()` | Model layer loading | Asserts includes "## Model: qwen3-coder-30b", model content present, "model:qwen3-coder-30b" in layers list |
| `test_load_instructions_with_custom_param()` | Custom parameter override | Asserts includes "## Custom Instructions", custom content present, "custom" in layers list |
| `test_load_instructions_with_workspace_agent_md()` | Workspace detection | Asserts includes "## Project Instructions", workspace content present, "workspace" in layers list |
| `test_load_instructions_full_stack()` | All layers combined | Asserts all 5 section headers present, correct order, all layers tracked in result.layers |
| `test_user_overrides_built_in()` | User override behavior | Asserts user instruction file used instead of built-in |
| `test_workspace_agent_md_found()` | Workspace file found | Asserts returns Path object when file exists |
| `test_workspace_agent_md_not_found()` | Workspace file missing | Asserts returns None when file doesn't exist |
| `test_workspace_agent_md_none_workspace()` | None workspace handling | Asserts returns None when workspace is None |
| `test_instruction_layer_order()` | Correct layer ordering | Asserts base < provider < model < custom < workspace in final prompt |
| `test_empty_layer_skipped()` | Empty layer behavior | Asserts files with empty body don't add section headers |

### Integration Tests (test_instructions_integration.py)

| Test Function | Verifies | Key Assertions |
|---------------|----------|----------------|
| `test_prompt_nano_agent_with_custom_instructions()` | End-to-end custom instructions | Asserts agent executes, custom instructions loaded, response successful, metadata includes instruction_layers |
| `test_prompt_nano_agent_with_workspace_agent_md()` | End-to-end workspace detection | Asserts workspace AGENT.md loaded, agent aware of project context, metadata includes "workspace" layer |
| `test_prompt_nano_agent_backward_compatible()` | Existing calls unchanged | Asserts calls without `instructions` parameter work as before |
| `test_prompt_nano_agent_instruction_layers_in_metadata()` | Metadata recording | Asserts response metadata.instruction_layers includes list of loaded layers (e.g., ["base", "provider:ollama", "model:qwen3-coder-30b"]) |
| `test_prompt_nano_agent_with_provider_model_combinations()` | Multiple providers/models | Tests all 5 providers × 3 models = 15 combinations |
| `test_prompt_nano_agent_graceful_degradation()` | Missing files handling | Asserts agent executes even when all instruction files missing |

### Test Coverage Requirements

- **Line coverage**: >90% for `instructions.py` module
- **Branch coverage**: >85% for all conditional branches
- **Integration coverage**: All provider/model combinations tested
- **Edge case coverage**: All negative scenarios and edge cases have tests

## Files to Create/Modify

### New Files to Create

| File Path | Purpose | Key Content |
|-----------|---------|-------------|
| `apps/nano_agent_mcp_server/src/nano_agent/modules/instructions.py` | Core instruction loading module | `InstructionLoader` class, `InstructionResult` dataclass, file reading, YAML parsing, 4-layer resolution |
| `apps/nano_agent_mcp_server/src/nano_agent/instructions/README.md` | Documentation | Instruction file format, examples, how to create custom instructions |
| `apps/nano_agent_mcp_server/src/nano_agent/instructions/openai.md` | OpenAI provider instructions | OpenAI-specific prompting guidance, function calling best practices |
| `apps/nano_agent_mcp_server/src/nano_agent/instructions/anthropic.md` | Anthropic provider instructions | Claude-specific guidance, XML thinking format |
| `apps/nano_agent_mcp_server/src/nano_agent/instructions/ollama.md` | Ollama provider instructions | Local model guidance, latency considerations |
| `apps/nano_agent_mcp_server/src/nano_agent/instructions/lmstudio.md` | LM Studio provider instructions | Local model guidance, OpenAI-compatible API, multiple models support |
| `apps/nano_agent_mcp_server/src/nano_agent/instructions/zai.md` | Z.ai provider instructions | GLM model guidance, bilingual support |
| `apps/nano_agent_mcp_server/src/nano_agent/instructions/glm-4.7.md` | GLM-4.7 model instructions | GLM-4.7 specific optimization, strong reasoning |
| `apps/nano_agent_mcp_server/src/nano_agent/instructions/qwen3-coder-30b.md` | Qwen3-Coder model instructions | Code generation focus, Python/JavaScript optimization |
| `apps/nano_agent_mcp_server/src/nano_agent/instructions/gpt-5-mini.md` | GPT-5-mini model instructions | Fast execution, simple tasks, cost efficiency |
| `apps/nano_agent_mcp_server/src/nano_agent/instructions/claude-opus-4-20250514.md` | Claude Opus 4 model instructions | Complex reasoning, long context, careful analysis |
| `apps/nano_agent_mcp_server/tests/test_instructions.py` | Unit tests | All unit tests for instruction loading |
| `apps/nano_agent_mcp_server/tests/test_instructions_integration.py` | Integration tests | End-to-end tests for instruction system |

### Existing Files to Modify

| File Path | Changes | Lines Affected |
|-----------|---------|----------------|
| `apps/nano_agent_mcp_server/src/nano_agent/modules/constants.py` | Add instruction directory path constants | Add after line 80 (before NANO_AGENT_SYSTEM_PROMPT) |
| `apps/nano_agent_mcp_server/src/nano_agent/modules/data_types.py` | Add `instructions` parameter to `PromptNanoAgentRequest` | Add after line 32 (after `workspace` field) |
| `apps/nano_agent_mcp_server/src/nano_agent/modules/nano_agent.py` | Import `InstructionLoader`, replace instruction building | Lines ~23 (import), 348-349 (async), 485-486 (sync), 576 (function signature) |
| `apps/nano_agent_mcp_server/pyproject.toml` | Add PyYAML dependency | Add `pyyaml>=6.0` to dependencies array (line 10) |

## Migration / Backward Compatibility

### Zero-Impact Guarantee

This feature is **100% backward compatible**. Existing users experience no breaking changes:

1. **Existing calls work unchanged**:
   ```python
   # These existing calls continue to work exactly as before
   await prompt_nano_agent("Write a function")
   await prompt_nano_agent("Analyze code", model="gpt-5-mini", provider="openai")
   ```

2. **Default behavior is enhanced, not changed**:
   - When `instructions=None` (default), system auto-loads provider/model instructions
   - Base prompt (`NANO_AGENT_SYSTEM_PROMPT`) is always included
   - If no instruction files exist, falls back to current behavior (base prompt only)

3. **No new required configuration**:
   - Users don't need to create any files
   - Built-in instructions ship with the package
   - `~/.nano-agent/instructions/` directory created automatically if needed

4. **No API breaking changes**:
   - `instructions` parameter is optional (defaults to `None`)
   - Existing parameters (`agentic_prompt`, `model`, `provider`, `workspace`) unchanged
   - Response structure unchanged (same fields in `PromptNanoAgentResponse`)

### Migration Path for Users Who Want Custom Instructions

Users who want custom instructions can opt-in gradually:

1. **Create user instructions directory**:
   ```bash
   mkdir -p ~/.nano-agent/instructions
   ```

2. **Create custom instruction file**:
   ```bash
   # Create ~/.nano-agent/instructions/python-expert.md
   cat > ~/.nano-agent/instructions/python-expert.md << 'EOF'
   ---
   version: "1.0"
   author: "user@example.com"
   description: "Python expert instructions"
   ---
   
   You are a Python expert. Focus on:
   - Type hints and dataclasses
   - Context managers and async/await
   - PEP 8 compliance
   EOF
   ```

3. **Use custom instructions**:
   ```python
   # Opt-in to custom instructions
   await prompt_nano_agent("Refactor this code", instructions="python-expert")
   ```

4. **Add workspace-level instructions** (optional):
   ```bash
   # Create /path/to/project/AGENT.md
   echo "# Project Specific Rules" > /path/to/project/AGENT.md
   ```

### Rollback Plan

If issues arise, the feature can be temporarily disabled:

1. **Set environment variable** (if feature flag added):
   ```bash
   export NANO_AGENT_DISABLE_INSTRUCTIONS=true
   ```

2. **Or revert to base-only behavior**:
   - Pass `instructions=""` (empty string) to skip all layers except base
   - Or delete built-in instruction files (keeps loader logic but uses base only)

3. **No data loss or migration needed**:
   - Instruction files are additive only
   - No existing configuration files modified
   - No database or state changes

## Example Usage

### Example 1: Basic Usage (Auto-Load Provider/Model Instructions)

```python
from nano_agent import prompt_nano_agent

# Agent automatically loads Ollama + Qwen3-Coder instructions
result = await prompt_nano_agent(
    "Create a FastAPI endpoint with CRUD operations for users",
    provider="ollama",
    model="qwen3-coder:30b",
    workspace="/tmp/myapi"
)

# System prompt assembled as:
# ## Base Instructions
# {NANO_AGENT_SYSTEM_PROMPT}
#
# ## Provider: ollama
# {Instructions for local Ollama models}
#
# ## Model: qwen3-coder:30b
# {Instructions optimized for Qwen3-Coder code generation}
#
# Workspace directory: /tmp/myapi
```

### Example 2: Custom Instructions for Specific Task Type

```python
# User created ~/.nano-agent/instructions/tdd.md with TDD workflow
result = await prompt_nano_agent(
    "Implement a user authentication system",
    provider="zai",
    model="glm-4.7",
    instructions="tdd",  # Load TDD-specific instructions
    workspace="/tmp/auth-system"
)

# System prompt includes:
# ## Base Instructions
# ...
#
# ## Provider: zai
# ...
#
# ## Model: glm-4.7
# ...
#
# ## Custom Instructions
# {TDD workflow: write tests first, red-green-refactor, etc.}
```

### Example 3: Workspace-Level Project Instructions

```python
# Project has /tmp/myproject/AGENT.md with project conventions
result = await prompt_nano_agent(
    "Add a new feature to the existing codebase",
    provider="openai",
    model="gpt-5-mini"
)

# System prompt includes:
# ## Base Instructions
# ...
#
# ## Provider: openai
# ...
#
# ## Model: gpt-5-mini
# ...
#
# ## Project Instructions
# {Project-specific rules from AGENT.md:
#  - Use TypeScript strict mode
#  - Follow our naming conventions
#  - Run tests before committing}
```

### Example 4: All Layers Combined (Maximum Customization)

```python
# All customization options used together
result = await prompt_nano_agent(
    "Build a complete microservice with database, API, and tests",
    provider="lmstudio",
    model="qwen3-coder-next",
    instructions="microservice-expert",  # User's custom instruction set
    workspace="/tmp/microservice"
)

# System prompt includes all 5 layers:
# ## Base Instructions
# {General agent workflow and tools}
#
# ## Provider: lmstudio
# {Local model guidance}
#
# ## Model: qwen3-coder-next
# {Code generation optimization}
#
# ## Custom Instructions
# {User's microservice expertise: DDD, event sourcing, etc.}
#
# ## Project Instructions
# {From /tmp/microservice/AGENT.md:
#  - Use PostgreSQL
#  - Follow our folder structure
#  - Include OpenAPI spec}
#
# Workspace directory: /tmp/microservice
```

### Example 5: Backward Compatibility (Existing Code Works Unchanged)

```python
# Existing v1.x code continues to work without modification
result = await prompt_nano_agent(
    "Create a Python script to process CSV files"
)

# Automatically loads OpenAI + GPT-5-mini instructions
# No changes needed to existing code
```

### Example 6: Graceful Degradation (Missing Instruction Files)

```python
# Even if instruction files don't exist, agent works
result = await prompt_nano_agent(
    "Simple task",
    provider="ollama",
    model="unknown-model"  # No instruction file for this model
)

# System prompt:
# ## Base Instructions
# {NANO_AGENT_SYSTEM_PROMPT}
#
# (No provider/model layers because files don't exist)
# (Agent still executes successfully with base prompt only)
```

---

**End of Spec 01: Agent Instructions System**
