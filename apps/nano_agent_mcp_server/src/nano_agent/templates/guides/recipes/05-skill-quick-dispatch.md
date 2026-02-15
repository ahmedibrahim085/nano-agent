# Recipe 05: Skill Quick Dispatch

Create a reusable Claude Code skill that dispatches tasks to external LLMs via nano-agent. Invoke it with a slash command like `/nano-dispatch`. Ideal for frequent one-off patterns like "review this function" or "analyze this error".

## Use Case

Use this when:
- You frequently dispatch the same type of task to external LLMs
- You want a one-command solution for common AI operations
- You want to share dispatch patterns with your team
- You want convenience over full control

## How It Works

Claude Code skills are `.md` files in `~/.claude/skills/{skill-name}/SKILL.md` (global) or `.claude/skills/{skill-name}/SKILL.md` (project). Claude Code auto-discovers them and makes them available as `/skill-name` slash commands.

## Steps

### 1. Create the Skill Directory

```bash
mkdir -p ~/.claude/skills/nano-dispatch
```

### 2. Write the SKILL.md File

Create `~/.claude/skills/nano-dispatch/SKILL.md`:

```markdown
# Skill: Nano Dispatch

Quick dispatch for one-off tasks to an external LLM via nano-agent.

## Usage
/nano-dispatch <task description>

## Instructions

When the user invokes this skill:

1. Take the user's task description from the arguments
2. Dispatch it to an external LLM using:

mcp__nano-agent__prompt_nano_agent(
  agentic_prompt="<user's task description>",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace="<current project directory>"
)

3. Report the result back to the user

## Notes
- Replace YOUR_MODEL and YOUR_PROVIDER with your preferred model/provider
- The agent has file access within the workspace (read, write, edit, bash, git)
- Each dispatch is stateless — include all context in the prompt
```

### 3. Use the Skill

After creating the file, invoke it in Claude Code:

```
/nano-dispatch Review src/auth/middleware.py for security vulnerabilities
```

Claude Code reads the SKILL.md instructions and dispatches accordingly.

## Example: Code Review Skill

`~/.claude/skills/nano-review/SKILL.md`:

```markdown
# Skill: Nano Review

Dispatch a code review to an external LLM.

## Usage
/nano-review <file or directory path>

## Instructions

When invoked:

1. Read the target file/directory path from arguments
2. Dispatch a review:

mcp__nano-agent__launch_agent(
  agentic_prompt="Review all files at <path> for:
    1. Security vulnerabilities
    2. Performance issues
    3. Code quality and maintainability
    Return findings by severity with file:line references.",
  agent_path="/path/to/agents/code-reviewer",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace="<current project directory>"
)

3. Present the review findings to the user
```

## Example: Test Generator Skill

`~/.claude/skills/nano-test/SKILL.md`:

```markdown
# Skill: Nano Test

Generate unit tests for a function or file using an external LLM.

## Usage
/nano-test <file path>

## Instructions

When invoked:

1. Read the target file path from arguments
2. Dispatch test generation:

mcp__nano-agent__prompt_nano_agent(
  agentic_prompt="Read <file path> and generate comprehensive unit tests.
    Cover normal cases, edge cases, and error conditions.
    Use the project's testing framework.
    Write tests to tests/ directory following existing conventions.",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace="<current project directory>"
)

3. Report which test files were created
```

## Example: Error Analyzer Skill

`~/.claude/skills/nano-debug/SKILL.md`:

```markdown
# Skill: Nano Debug

Analyze an error message using an external LLM.

## Usage
/nano-debug <error message or description>

## Instructions

When invoked:

1. Take the error description from arguments
2. Dispatch analysis:

mcp__nano-agent__prompt_nano_agent(
  agentic_prompt="Analyze this error and suggest fixes:
    <error description>

    Check the codebase for the root cause. Provide:
    1. Root cause explanation
    2. Exact file and line causing the issue
    3. Concrete fix with code",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace="<current project directory>"
)

3. Present the diagnosis and fix to the user
```

## Important Notes

- **No CLI install command**: Skills are just files — copy the SKILL.md to the right directory
- **Skill paths**: `~/.claude/skills/{name}/SKILL.md` (global) or `.claude/skills/{name}/SKILL.md` (project-local)
- **Auto-discovery**: Claude Code finds skills automatically from these standard directories
- **Cost**: Depends on the target model (free for local, pay-per-token for cloud)
- **Customization**: Edit YOUR_MODEL/YOUR_PROVIDER in each SKILL.md to match your setup

## When NOT to Use This Recipe

- For one-time unique tasks with no reuse potential → use `prompt_nano_agent` directly (Recipe 01)
- For complex multi-step workflows → use Teammate (Recipe 02) or `launch_agent` (Recipe 04)
- When you need full control over parameters each time → manual MCP tool call is better
