# Recipe 01: MCP Direct Dispatch

Dispatch a self-contained task to any external LLM using `prompt_nano_agent`. Best for single-round tasks where you control model selection.

## Use Case

Use this when:
- You need a specific external LLM (not Claude Code itself)
- The task is self-contained (no multi-turn needed)
- You want direct control over model/provider
- Cost transparency is important (free for local models)

## Steps

### 1. Check Available Providers

First, verify which providers and models are available:

```
mcp__nano-agent__check_providers()
```

Returns a dictionary with each provider's status, available models, and latency.

### 2. Dispatch a Task

Use `prompt_nano_agent` with a detailed prompt:

```
mcp__nano-agent__prompt_nano_agent(
  agentic_prompt="You are a senior Python developer. Analyze src/utils/helper.py and identify:
    1. Security vulnerabilities
    2. Performance optimization opportunities
    3. Code style issues per PEP 8
    Return a structured report with severity ratings.",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace="/path/to/project"
)
```

**Parameters:**
| Parameter | Required | Description |
|-----------|----------|-------------|
| `agentic_prompt` | Yes | Natural language task description |
| `model` | No | Model name (defaults to server config) |
| `provider` | No | Provider name: `openai`, `anthropic`, `ollama`, `lmstudio`, `zai`, `qwen` |
| `workspace` | No | Working directory for file operations (defaults to cwd) |

### 3. Read the Response

The tool returns a `Dict[str, Any]` with these keys:

```json
{
  "success": true,
  "result": "Created report.md with 3 vulnerabilities found...",
  "error": null,
  "metadata": { "model": "YOUR_MODEL", "provider": "YOUR_PROVIDER" },
  "execution_time_seconds": 12.5
}
```

Check `success` first. If `false`, read `error` for details.

## Example: Implement a Utility Function

**Scenario**: You need a TypeScript utility function implemented by an external LLM.

```
mcp__nano-agent__prompt_nano_agent(
  agentic_prompt="Implement a TypeScript debounce utility function in src/utils/debounce.ts.

    Requirements:
    1. Generic type signature: debounce<T extends (...args: any[]) => any>(func: T, wait: number): T
    2. Use setTimeout and clearTimeout
    3. Support leading/trailing edge execution
    4. Return cancel function
    5. Include JSDoc comments",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace="/path/to/project"
)
```

The agent will read existing files, create `src/utils/debounce.ts`, and verify it compiles.

## Example: Code Review

**Scenario**: Review a Python file for best practices.

```
mcp__nano-agent__prompt_nano_agent(
  agentic_prompt="Review src/main.py for:
    1. Type safety issues (missing type hints)
    2. Error handling gaps
    3. Potential bugs

    Return findings in this format:
    ## Issues Found
    - [Critical/Warning/Info] Issue description

    ## Suggested Fixes
    1. Fix for issue 1
    2. Fix for issue 2",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace="/path/to/project"
)
```

## Important Notes

- **Stateless**: Each call is independent — embed all needed context in the prompt
- **File access**: The agent has 13 tools (read/write/edit files, bash, git, etc.) within the workspace
- **Cost**: Free for local models (Ollama, LM Studio), pay-per-token for cloud providers
- **Latency**: Single roundtrip — fastest execution mechanism
- **No `context` parameter**: All context goes in `agentic_prompt` (or write to a file and tell the agent to read it)

## When NOT to Use This Recipe

- For multi-turn conversations with persistent identity → use `launch_agent` (Recipe 04)
- For Claude Code subagent collaboration → use Teammate (Recipe 02)
- For shell commands without AI → use Background Bash (Recipe 03)
