# Nano-Agent Skill Templates

Skill templates that extend Claude Code with nano-agent dispatch capabilities via slash commands.

## What Are Skills?

Skills are reusable prompts invoked as `/skill-name` commands. Unlike agents (which run in a separate context), skills run in your main conversation and inject instructions inline.

## Available Templates

| Template | Slash Command | Purpose |
|----------|---------------|---------|
| `nano-dispatch/` | `/nano-dispatch <task>` | Quick one-off dispatch to an external LLM |

## Installation

### Personal (available in all your projects)

```bash
cp -r templates/skills/nano-dispatch ~/.claude/skills/
```

### Project-level (shared with team via version control)

```bash
cp -r templates/skills/nano-dispatch .claude/skills/
```

## Customization

After copying, edit `SKILL.md` to set your preferred model and provider in the dispatch call. See `templates/agents/README.md` for the full provider/model reference.

## Skills vs Agents: Key Differences

| Aspect | Skills (`SKILL.md`) | Agents (`.md` in `agents/`) |
|--------|---------------------|----------------------------|
| Runs in | Main conversation context | Separate context window |
| Invoked via | `/skill-name` or auto by Claude | Claude delegates automatically |
| Tool control | `allowed-tools` (auto-approve list) | `tools` (available tool list) |
| Arguments | `$ARGUMENTS` substitution | Via Claude's delegation prompt |

The `allowed-tools` field in skills means "tools Claude can use **without asking permission**" while the skill is active. The `tools` field in agents means "tools the agent **has access to**."

## Creating Your Own Skills

Minimum viable skill:

```yaml
---
name: my-skill
description: What this skill does
allowed-tools: Read, Bash, mcp__nano-agent__prompt_nano_agent
---

Instructions for Claude when this skill is invoked.
Use $ARGUMENTS to reference what the user types after /my-skill.
```

See the [Claude Code skills docs](https://code.claude.com/docs/en/skills) for all options.

## Prerequisites

The nano-agent MCP server must be registered in your Claude Code settings. See `templates/agents/README.md` for setup instructions.
