# Nano-Agent Templates

Starter templates for integrating nano-agent with Claude Code.

## Categories

| Directory | Contents | Used By |
|-----------|----------|---------|
| `agents/` | Claude Code agent templates (YAML frontmatter) | Claude Code subagent system |
| `skills/` | Claude Code skill templates (slash commands) | Claude Code `/skill-name` invocation |
| `agent-identities/` | AGENT.md identity files for external LLMs | `launch_agent` MCP tool |
| `guides/` | Decision guides and step-by-step recipes | Human reference / Claude context |

## Installation

Templates are bundled inside the nano-agent package. After `uv tool install` or `pip install`, they're accessible via MCP resources:

```
ListMcpResourcesTool(server="nano-agent")
ReadMcpResourceTool(server="nano-agent", uri="nano-agent://templates/agents/nano-reviewer.md")
```

To install a template locally, copy it from the package source:

```bash
# Example: install an agent template
cp src/nano_agent/templates/agents/nano-reviewer.md ~/.claude/agents/
```

See each category's README for specific installation instructions.
