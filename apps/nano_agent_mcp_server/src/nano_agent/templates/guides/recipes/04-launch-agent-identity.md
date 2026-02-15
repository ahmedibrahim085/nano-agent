# Recipe 04: Launch Agent with Identity

Use `launch_agent` to dispatch tasks to an external LLM with a persistent identity defined in an AGENT.md file. Best when you need consistent agent behavior and role-specific expertise.

## Use Case

Use this when:
- You need consistent agent behavior defined by a role (TDD engineer, security reviewer, etc.)
- Multiple tasks should share the same persona and guidelines
- You want to avoid repeating role instructions in every prompt
- The agent needs domain-specific expertise layered on top of base tools

## How It Works

`launch_agent` reads an AGENT.md file and builds a three-layer system prompt:
1. **Base Layer**: Core tools and behavioral rules (13 tools: read/write/edit files, bash, git, etc.)
2. **Agent Layer**: Role-specific persona from AGENT.md
3. **Project Layer**: Optional project-specific context from workspace/AGENT.md

## Steps

### 1. Create an AGENT.md Identity File

Create a directory with an `AGENT.md` file anywhere on your filesystem:

```bash
mkdir -p /path/to/agents/tdd-engineer
```

Write the identity file (`/path/to/agents/tdd-engineer/AGENT.md`):

```markdown
# Agent Identity: TDD Engineer

You are an expert Test-Driven Development engineer.

## Responsibilities
- Write comprehensive unit tests before implementation
- Follow strict RED-GREEN-REFACTOR discipline
- Ensure 80%+ code coverage
- Review test quality and coverage gaps

## Work Style
- Always write a failing test first
- Use the project's testing framework
- Follow AAA pattern: Arrange, Act, Assert
- Include edge cases and error conditions

## Quality Standards
- Tests must run fast (<100ms each)
- Avoid test interdependencies
- Use fixtures and parametrize for multiple inputs
- Mock external dependencies
```

### 2. Launch the Agent

Each task is a separate `launch_agent` call. The agent is **stateless** — it reads AGENT.md fresh each time:

```
mcp__nano-agent__launch_agent(
  agentic_prompt="Write unit tests for the filter_positive function in src/utils/numbers.py.
    Cover normal cases, empty list, single element, zero, negative numbers, and very large values.
    Use parametrize for multiple test cases.",
  agent_path="/path/to/agents/tdd-engineer",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace="/path/to/project"
)
```

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `agentic_prompt` | Yes | The task to perform |
| `agent_path` | Yes | Path to directory containing AGENT.md |
| `model` | No | Model name (defaults to server config) |
| `provider` | No | Provider name: `openai`, `anthropic`, `ollama`, `lmstudio`, `zai`, `qwen` |
| `workspace` | No | Working directory for file operations |

### 3. Read the Response

Returns a `Dict[str, Any]` — same structure as `prompt_nano_agent`:

```json
{
  "success": true,
  "result": "Created tests/test_numbers.py with 12 test cases covering all edge cases",
  "error": null,
  "metadata": { "model": "YOUR_MODEL", "provider": "YOUR_PROVIDER" },
  "execution_time_seconds": 18.3
}
```

### 4. Send Another Task (Same Identity)

Each call is independent but uses the same AGENT.md persona:

```
mcp__nano-agent__launch_agent(
  agentic_prompt="Write unit tests for the validate_email function in src/utils/validation.py.
    Include: valid emails, invalid formats, edge cases (empty string, unicode, very long input).",
  agent_path="/path/to/agents/tdd-engineer",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace="/path/to/project"
)
```

## Example: Security Reviewer Identity

**AGENT.md** (`/path/to/agents/security-reviewer/AGENT.md`):

```markdown
# Agent Identity: Security Reviewer

You are a senior security engineer specializing in finding vulnerabilities.

## Focus Areas
1. Input validation and sanitization
2. Authentication/Session management
3. Cryptographic practices
4. Error handling (no info leakage)
5. SQL injection, XSS, CSRF

## Output Format
### Critical Issues
- [CWE ID] Issue description (file:line)

### Warnings
- Issue description

### Recommendations
1. Suggested improvement
```

**Usage:**

```
mcp__nano-agent__launch_agent(
  agentic_prompt="Review all files in src/api/ for security vulnerabilities. Check authentication logic, input validation, and SQL query construction.",
  agent_path="/path/to/agents/security-reviewer",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace="/path/to/project"
)
```

## Example: Documentation Specialist

**AGENT.md** (`/path/to/agents/doc-specialist/AGENT.md`):

```markdown
# Agent Identity: Documentation Specialist

You are an expert technical writer focused on code documentation.

## Standards
- Follow Google Python docstring style
- Include type hints in docs
- Add usage examples for public APIs
- Document edge cases and error conditions
```

**Usage:**

```
mcp__nano-agent__launch_agent(
  agentic_prompt="Add comprehensive docstrings to all public functions in src/core/engine.py",
  agent_path="/path/to/agents/doc-specialist",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace="/path/to/project"
)
```

## Important Notes

- **Stateless**: Each `launch_agent` call is independent — no state carries between calls
- **No `.dispatch()` method**: The tool returns a `Dict`, not an object with methods
- **Agent path flexibility**: Store AGENT.md anywhere; just pass the directory path to `agent_path`
- **Bundled templates**: nano-agent ships with 4 identity templates (general-coder, code-reviewer, tdd-engineer, backend-expert) accessible via MCP resources
- **Cost**: Free for local models, pay-per-token for cloud providers

## When NOT to Use This Recipe

- For one-time tasks without role consistency → use `prompt_nano_agent` (Recipe 01)
- For multi-agent team collaboration → use Teammate (Recipe 02)
- For shell commands without AI → use Background Bash (Recipe 03)
