# Nano-Agent Templates

Starter templates for integrating nano-agent with Claude Code.

## Categories

| Directory | Contents | Used By |
|-----------|----------|---------|
| `agents/` | Claude Code agent templates (YAML frontmatter) | Claude Code subagent system |
| `skills/` | Claude Code skill templates (slash commands) | Claude Code `/skill-name` invocation |
| `agent-identities/` | AGENT.md identity files for external LLMs | `launch_agent` MCP tool |
| `guides/` | Decision guides and step-by-step recipes | Human reference / Claude context |

## Getting Started

1. **Browse templates** via MCP resources:
   ```
   ListMcpResourcesTool(server="nano-agent")
   ```

2. **Read a template**:
   ```
   ReadMcpResourceTool(server="nano-agent", uri="nano-agent://templates/agents/nano-reviewer.md")
   ```

3. **Install it** — copy to the appropriate directory. See the [Installation Guide](guides/installation.md) for where each file type goes.

4. **Customize** — replace `YOUR_MODEL` and `YOUR_PROVIDER` placeholders with your preferred model and provider.

## Guides

| Guide | What It Covers |
|-------|---------------|
| [When to Use What](guides/when-to-use-what.md) | Decision guide for choosing execution mechanisms |
| [Installation](guides/installation.md) | Where each template file goes |
| [Multi-Instance](guides/multi-instance.md) | Running multiple agents without collisions |
| [Team Patterns](guides/team-patterns.md) | Ready-to-use team compositions |
| [Recipes](guides/recipes/) | Step-by-step recipes for 5 common patterns |

## Installation (Package Level)

Templates are bundled inside the nano-agent package. After `uv tool install` or `pip install`, they're accessible via MCP resources. To install a template locally:

```bash
# Example: install an agent template
cp src/nano_agent/templates/agents/nano-reviewer.md ~/.claude/agents/
```

See each category's README and the [Installation Guide](guides/installation.md) for specific instructions.
