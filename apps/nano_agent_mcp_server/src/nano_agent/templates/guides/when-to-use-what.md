# When to Use What: Nano-Agent Execution Mechanisms

Choosing the right execution mechanism is critical for efficiency, cost control, and task success. This guide helps you decide which approach to use based on your specific needs.

## Decision Tree

Start here to narrow down your options:

```
Is the task for a specific external LLM?
├─ Yes → Do you need multi-turn conversation with consistent identity?
│   ├─ Yes → launch_agent (MCP with identity)
│   └─ No → prompt_nano_agent (MCP direct)
└─ No → Is the task part of an ongoing collaboration?
    ├─ Yes → Teammate (Claude Code subagent)
    └─ No → Do you need immediate result?
        ├─ Yes → Subagent (Task tool)
        └─ No → Background Agent (Task tool, background)
```

## The 7 Mechanisms Comparison

| Mechanism | When to Use | Cost | Latency | Multi-turn |
|-----------|-------------|------|---------|------------|
| **prompt_nano_agent** (MCP direct) | Self-contained task on specific model. No persistent context needed. | Free for local models, pay-per-token for cloud | Low (single roundtrip) | No |
| **launch_agent** (MCP with identity) | Consistent agent behavior across tasks. Uses AGENT.md for role definition. | Free for local models, pay-per-token for cloud | Medium (agent startup) | Yes |
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
| Long-running build or test suite | Background Bash with `run_in_background=true` |
| Frequent dispatch via slash command | Skill (/nano-dispatch) |
| Multiple AI tasks in parallel | Background Agent (Task tool, background) |

## Common Patterns

### 1. Implement + Review
```markdown
1. Use prompt_nano_agent to implement initial code
2. Use launch_agent with reviewer identity to review and suggest improvements
3. Iterate until satisfied
```

### 2. Parallel Team Pattern
```markdown
1. Create multiple subagents with different specializations
2. Dispatch tasks in parallel using Task tool (background mode)
3. Collect results and synthesize
```

### 3. Research → Implement
```markdown
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
3. **Context needs**: Multi-turn needs Teammate or launch_agent with identity

When in doubt, start simple (prompt_nano_agent) and scale up complexity only if needed.
