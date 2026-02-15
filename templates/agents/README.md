# Nano-Agent Templates

Agent templates for Claude Code that dispatch work to external LLMs via the nano-agent MCP server.

## What Are These?

These are **starter templates** — not managed agents. Copy one, customize it, and save it where you need it. Each template defines a **role** (what the agent does) independently from the **model** (which LLM it dispatches to). Multiple templates can be installed side by side — each has a unique `name` field and lives in its own file, so they never overwrite each other. The nano-agent project owns the MCP server; agent and skill setup is entirely your domain.

## Installation

### Personal (available in all your projects)

```bash
cp templates/agents/nano-reviewer.md ~/.claude/agents/
```

### Project-level (shared with team via version control)

```bash
cp templates/agents/nano-reviewer.md .claude/agents/
```

Rename the file to match your use case (e.g., `cp nano-teammate.md my-zai-peer.md`). The `name` field inside the file — not the filename — is what Claude uses to identify the agent.

### Session-only (not saved to disk)

Pass agent configuration as JSON when launching Claude Code:

```bash
claude --agents '{
  "nano-reviewer": {
    "description": "Code reviewer with nano-agent dispatch",
    "prompt": "You review code by combining your analysis with an external LLM review via nano-agent...",
    "tools": ["Read", "Grep", "Glob", "Bash", "mcp__nano-agent__prompt_nano_agent"],
    "model": "inherit"
  }
}'
```

See the [CLI reference](https://code.claude.com/docs/en/cli-reference) for the full JSON format.

## Available Templates

| Template | Role | Best For |
|----------|------|----------|
| `nano-reviewer.md` | Code review with external LLM cross-check | Post-change review, PR review |
| `nano-researcher.md` | Codebase research with external LLM analysis | Architecture exploration, dependency mapping |
| `nano-implementer.md` | Code implementation via external LLM dispatch | Feature development, bug fixes |
| `nano-teammate.md` | Peer teammate for agent teams | Multi-agent collaboration, debates |

## Customization

### Change the dispatch model

Every template includes a dispatch section like:

```
mcp__nano-agent__prompt_nano_agent(
  agentic_prompt="...",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace=""
)
```

Replace `YOUR_MODEL` and `YOUR_PROVIDER` with your preferred LLM:

| Provider | Models | Auth |
|----------|--------|------|
| `openai` | `gpt-5`, `gpt-5-mini`, `gpt-5-nano`, `gpt-4o` | `OPENAI_API_KEY` |
| `anthropic` | `claude-opus-4-1-20250805`, `claude-opus-4-20250514`, `claude-sonnet-4-20250514`, `claude-3-haiku-20240307` | `ANTHROPIC_API_KEY` |
| `ollama` | `gpt-oss:20b`, `gpt-oss:120b`, `qwen3-coder:30b`, `magistral:latest` | None (local) |
| `lmstudio` | Dynamic (queries local API at `127.0.0.1:1234`) | None (local) |
| `zai` | `glm-5`, `glm-4.7`, `glm-4.5-air` | `Z_AI_API_KEY` |
| `qwen` | `coder-model` | Requires prior `qwen` CLI authentication |

Anthropic models require full date-suffixed names (e.g., `claude-sonnet-4-20250514`, not `claude-sonnet-4`).

### Change the agent's own model

The `model:` frontmatter field controls which Claude model runs the **agent itself** (not the dispatched LLM). All templates default to `model: inherit` (same model as your main conversation). Override it to control cost:

```yaml
model: inherit   # Same as main conversation (default)
model: sonnet    # Balanced capability and cost — good for teammates
model: haiku     # Fast and cheap — good for focused tasks
model: opus      # Most capable — for complex reasoning
```

For agent teams, consider using `model: sonnet` to reduce token costs since each teammate runs as a separate Claude session.

### Add persistent memory

Add `memory: user` to the frontmatter for cross-session learning:

```yaml
---
name: my-reviewer
memory: user
---
```

Memory scopes: `user` (all projects), `project` (this repo), `local` (this repo, not version-controlled).

### Add project-specific context

Agents automatically load `CLAUDE.md` from the project root. For agent-specific context, use the `skills:` frontmatter field to preload skill content.

### Using with agent teams

When spawning a teammate, include task-specific context in the spawn prompt:

```
Create an agent team. Spawn a nano-teammate with the prompt:
"Your first task: review the authentication module at src/auth/ for
security vulnerabilities. Focus on token handling and session management.
The app uses JWT tokens stored in httpOnly cookies."
```

Teammates do NOT inherit conversation history from the lead, so include all relevant context in the spawn prompt. They DO automatically load `CLAUDE.md` and configured MCP servers.

## Advanced Configuration

These frontmatter fields are available but not included in the templates by default:

| Field | Purpose | Example |
|-------|---------|---------|
| `maxTurns` | Limit agent iterations to prevent runaway execution | `maxTurns: 30` |
| `permissionMode` | Control permission handling | `permissionMode: acceptEdits` |
| `disallowedTools` | Deny specific tools (denylist) | `disallowedTools: Write, Edit` |
| `hooks` | Lifecycle hooks for validation | See [hooks docs](https://code.claude.com/docs/en/hooks) |
| `skills` | Preload skill content into the agent | `skills: api-conventions` |
| `mcpServers` | Reference or inline MCP server configs | `mcpServers: nano-agent` |

See the [Claude Code subagents docs](https://code.claude.com/docs/en/sub-agents) for full details.

Any agent template can also run in the background via Ctrl+B during execution. Note: MCP tools (including nano-agent dispatch) are not available in background subagents — use foreground execution for dispatch-dependent workflows.

## Prerequisites

The nano-agent MCP server must be registered in your Claude Code settings (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "nano-agent": {
      "command": "nano-agent",
      "args": []
    }
  }
}
```

Verify with: `nano-agent --help` or ask Claude to use the `check_providers` tool.

The nano-agent MCP server provides 3 tools:
- `prompt_nano_agent` — dispatch a task to any supported model
- `launch_agent` — deploy an agent with an identity file (AGENT.md)
- `check_providers` — health check all configured providers

## Troubleshooting

### All providers show as down

If `check_providers` reports no available providers:

1. **Cloud providers** (openai, anthropic, zai): Set the required API key environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `Z_AI_API_KEY`)
2. **Ollama**: Ensure it's running (`ollama serve`) and accessible at `127.0.0.1:11434`
3. **LM Studio**: Ensure it's running with a model loaded, accessible at `127.0.0.1:1234`
4. **Qwen**: Authenticate via the `qwen` CLI first

See the main [nano-agent README](../../README.md) for full setup instructions.

### Agent not triggering

If Claude doesn't use your agent when expected:

1. Check the `description` field includes keywords matching your request
2. Run `/agents` to verify it's loaded
3. Try invoking it explicitly: "Use the nano-reviewer agent to review my changes"

## Creating Your Own

Start from any template or from scratch. The minimum viable agent:

```yaml
---
name: my-agent
description: What this agent does and when to use it
tools: Read, Grep, Glob, mcp__nano-agent__prompt_nano_agent
---

Your system prompt here. Tell the agent what role it plays,
how to dispatch work, and what to verify.
```
