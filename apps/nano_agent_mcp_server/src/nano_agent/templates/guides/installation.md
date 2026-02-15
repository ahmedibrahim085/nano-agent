# Installation Guide

Where each nano-agent template file goes and how Claude Code discovers them.

## File Placement

| Template Type | Location | Discovery |
|---------------|----------|-----------|
| **Agent templates** (Claude Code subagents) | `~/.claude/agents/` (global) or `.claude/agents/` (project) | Auto-discovered by Claude Code |
| **Skill templates** (slash commands) | `~/.claude/skills/{skill-name}/SKILL.md` (global) or `.claude/skills/{skill-name}/SKILL.md` (project) | Auto-discovered as `/{skill-name}` |
| **Agent identities** (AGENT.md for `launch_agent`) | Any path on your filesystem | Passed explicitly via `agent_path` parameter |

## Step-by-Step

### Installing an Agent Template

1. Read the template via MCP resource:
   ```
   ReadMcpResourceTool(server="nano-agent", uri="nano-agent://templates/agents/nano-reviewer.md")
   ```

2. Copy to your agents directory:
   ```bash
   cp nano-reviewer.md ~/.claude/agents/
   ```

3. Edit `YOUR_MODEL` and `YOUR_PROVIDER` placeholders to match your setup.

4. Claude Code auto-discovers it — the agent appears in the `Task` tool's `subagent_type` list.

### Installing a Skill Template

1. Read the template:
   ```
   ReadMcpResourceTool(server="nano-agent", uri="nano-agent://templates/skills/nano-dispatch/SKILL.md")
   ```

2. Create the skill directory and copy:
   ```bash
   mkdir -p ~/.claude/skills/nano-dispatch
   cp SKILL.md ~/.claude/skills/nano-dispatch/
   ```

3. Edit `YOUR_MODEL` and `YOUR_PROVIDER` in the SKILL.md.

4. Invoke with `/nano-dispatch` in Claude Code.

### Installing an Agent Identity (for launch_agent)

1. Read the template:
   ```
   ReadMcpResourceTool(server="nano-agent", uri="nano-agent://templates/agent-identities/tdd-engineer/AGENT.md")
   ```

2. Copy to any location you prefer:
   ```bash
   mkdir -p ~/agents/tdd-engineer
   cp AGENT.md ~/agents/tdd-engineer/
   ```

3. Reference via `agent_path` when calling `launch_agent`:
   ```
   mcp__nano-agent__launch_agent(
     agentic_prompt="...",
     agent_path="/Users/you/agents/tdd-engineer",
     model="YOUR_MODEL",
     provider="YOUR_PROVIDER"
   )
   ```

   There is no fixed location — `agent_path` accepts any valid directory path.

## Browsing Available Templates

List all templates via MCP:

```
ListMcpResourcesTool(server="nano-agent")
```

Read the full index:

```
ReadMcpResourceTool(server="nano-agent", uri="nano-agent://templates/index")
```

## After Editing YOUR_MODEL / YOUR_PROVIDER

Every template ships with `YOUR_MODEL` and `YOUR_PROVIDER` placeholders. Replace them with your preferred model and provider. Examples:

| Provider | Model Examples |
|----------|---------------|
| `openai` | `gpt-4o`, `gpt-5` |
| `anthropic` | `claude-sonnet-4-20250514` |
| `ollama` | `qwen3:32b`, `llama3:70b` |
| `lmstudio` | `qwen/qwen3-coder-next` |
| `zai` | `glm-5`, `glm-4.7` |
| `qwen` | `qwen-max` |

Run `mcp__nano-agent__check_providers()` to see which providers are available and what models they offer.
