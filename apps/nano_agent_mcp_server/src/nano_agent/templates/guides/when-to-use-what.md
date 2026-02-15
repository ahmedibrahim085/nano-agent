# When to Use What: Nano-Agent Execution Mechanisms

Choosing the right execution mechanism is critical for efficiency, cost control, and task success. This guide helps you decide which approach to use based on your specific needs.

## Goal-Oriented Lookup

**Start here** — find your goal and follow the recommendation:

| I Want To... | Use | Recipe |
|--------------|-----|--------|
| Dispatch a one-off coding task to an external LLM | `prompt_nano_agent` | [Recipe 01](recipes/01-mcp-direct-dispatch.md) |
| Get a code review from an external LLM | `launch_agent` with code-reviewer identity | [Recipe 04](recipes/04-launch-agent-identity.md) |
| Build a dev team with multiple agents | Teammate (TeamCreate + Task) | [Recipe 02](recipes/02-teammate-collaboration.md) |
| Run tests or builds in the background | Background Bash | [Recipe 03](recipes/03-background-bash.md) |
| Create a reusable slash command for dispatch | Skill (SKILL.md) | [Recipe 05](recipes/05-skill-quick-dispatch.md) |
| Use the same AI persona across multiple tasks | `launch_agent` with AGENT.md | [Recipe 04](recipes/04-launch-agent-identity.md) |
| Set up a team composition | See [Team Patterns](team-patterns.md) | — |
| Install templates into Claude Code | See [Installation Guide](installation.md) | — |
| Run multiple agents without conflicts | See [Multi-Instance Guide](multi-instance.md) | — |

## Decision Tree

```
Is the task for a specific external LLM?
├─ Yes → Do you need consistent identity across tasks?
│   ├─ Yes → launch_agent with AGENT.md (Recipe 04)
│   └─ No → prompt_nano_agent (Recipe 01)
└─ No → Is the task part of an ongoing collaboration?
    ├─ Yes → Teammate (Recipe 02)
    └─ No → Do you need immediate result?
        ├─ Yes → Subagent (Task tool)
        └─ No → Background Agent (Task tool, background)
```

## The 7 Mechanisms Comparison

| Mechanism | When to Use | Cost | Latency | Multi-turn |
|-----------|-------------|------|---------|------------|
| **prompt_nano_agent** (MCP direct) | Self-contained task on specific model. No persistent context needed. | Free for local models, pay-per-token for cloud | Low (single roundtrip) | No |
| **launch_agent** (MCP with identity) | Consistent agent behavior across tasks. Uses AGENT.md for role definition. | Free for local models, pay-per-token for cloud | Medium (agent startup) | No (stateless per call) |
| **Teammate** (Claude Code subagent) | Ongoing collaboration, multiple exchanges with sub-agent. Rich back-and-forth needed. | Paid (Claude Code) | Medium-High | Yes |
| **Subagent** (Task tool) | Quick focused task needing immediate result. Single-purpose AI worker. | Paid (Claude Code) | Medium | Limited |
| **Background Bash** | Long-running shell commands, no AI reasoning needed. Build, test, data processing. | Free | N/A (async) | No |
| **Skill** (/nano-dispatch) | Frequent one-off dispatch via slash command. Reusable dispatch patterns. | Depends on underlying model | Low | No |
| **Background Agent** (Task tool, background) | Parallel AI work, check later. Independent tasks running concurrently. | Paid (Claude Code) | Medium | Yes |

## Quick Reference Guide

| You Need... | Use |
|-------------|-----|
| Run a single query on specific model | `prompt_nano_agent` |
| Consistent agent behavior across tasks | `launch_agent` with AGENT.md |
| Multi-turn conversation with AI assistant | Teammate (Claude Code) |
| Quick focused task, get result now | Subagent (Task tool) |
| Long-running build or test suite | Background Bash with `run_in_background=True` |
| Frequent dispatch via slash command | Skill (/nano-dispatch) |
| Multiple AI tasks in parallel | Background Agent (Task tool, background) |

## Common Patterns

### 1. Implement + Review
```
1. Use prompt_nano_agent to implement initial code
2. Use launch_agent with reviewer identity to review and suggest improvements
3. Iterate until satisfied
```

### 2. Parallel Team Pattern
```
1. Create multiple subagents with different specializations
2. Dispatch tasks in parallel using Task tool (background mode)
3. Collect results and synthesize
```

### 3. Research → Implement
```
1. Use Subagent to research best practices on a topic
2. Extract key points and create prompt_nano_agent instructions
3. Dispatch final implementation to target model
```

## When NOT to Use What

- **Avoid prompt_nano_agent** for tasks requiring context persistence across multiple interactions
- **Avoid Teammate** for one-off quick tasks (overhead is too high)
- **Avoid Background Bash** for AI reasoning tasks (no LLM integration)
- **Avoid Skill** for one-time unique dispatches (setup overhead not worth it)

## Summary

Choose your mechanism based on three factors:

1. **Cost sensitivity**: Local models via prompt_nano_agent/launch_agent are free
2. **Latency requirements**: Direct dispatch is fastest, background jobs allow waiting
3. **Context needs**: Multi-turn needs Teammate; consistent persona needs launch_agent with AGENT.md

When in doubt, start simple (prompt_nano_agent) and scale up complexity only if needed.
