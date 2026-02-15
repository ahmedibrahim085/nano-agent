---
name: nano-dispatch
description: "Dispatch a task to an external LLM via nano-agent MCP. Use when you want to quickly send work to a nano-agent without setting up a full agent or teammate."
allowed-tools: mcp__nano-agent__prompt_nano_agent, mcp__nano-agent__check_providers, Read, Bash
---

# Nano-Agent Dispatch

Dispatch the following task to an external LLM via nano-agent:

**Task**: $ARGUMENTS

## Steps

1. If this is the first dispatch in this session, use the `check_providers` tool to verify available providers.
2. Read any files referenced in the task to understand context.
3. Dispatch:
   ```
   mcp__nano-agent__prompt_nano_agent(
     agentic_prompt="<expanded task with context from step 2>",
     model="YOUR_MODEL",
     provider="YOUR_PROVIDER",
     workspace=""  # uses current working directory
   )
   ```
4. Report the result. If the agent created or modified files, verify they exist and look correct.

## Customization

To use this skill, copy it to your personal or project skills directory:

```bash
# Personal (all projects)
cp -r templates/skills/nano-dispatch ~/.claude/skills/

# Project-level (this repo only)
cp -r templates/skills/nano-dispatch .claude/skills/
```

Then replace `YOUR_MODEL` and `YOUR_PROVIDER` with your preferred LLM.
Invoke with: `/nano-dispatch <your task description>`
