# Team Patterns

Ready-to-use team compositions for common workflows. Each pattern lists the files you need, how to spawn the team, and when to use it.

## Pattern 1: Lead + 2 Peers

**When**: You need parallel work with coordination. A lead delegates to two specialist teammates.

**Files needed:**
- `~/.claude/agents/nano-implementer.md` (or any agent template)
- `~/.claude/agents/nano-reviewer.md` (or any agent template)

**Spawn sequence:**

```
# 1. Create team
TeamCreate(team_name="dev-team", description="Implementation with review")

# 2. Create tasks
TaskCreate(
  subject="Implement feature X",
  description="Build the feature following existing patterns",
  activeForm="Implementing feature X"
)
TaskCreate(
  subject="Review feature X implementation",
  description="Review code quality, security, and test coverage",
  activeForm="Reviewing implementation"
)

# 3. Spawn teammates (embed first task in prompt to avoid idle-wake)
Task(
  subagent_type="nano-implementer",
  team_name="dev-team",
  name="impl",
  prompt="Claim the implementation task. Use mcp__nano-agent__prompt_nano_agent to dispatch coding work to YOUR_MODEL on YOUR_PROVIDER."
)

Task(
  subagent_type="nano-reviewer",
  team_name="dev-team",
  name="reviewer",
  prompt="Wait for the implementation task to complete, then claim the review task. Dispatch the review to YOUR_MODEL on YOUR_PROVIDER."
)
```

**Flow**: Lead creates tasks → impl works → reviewer reviews → lead synthesizes.

---

## Pattern 2: Implement → Review Pipeline

**When**: Sequential quality gate — code must pass review before merging.

**Files needed:**
- Any agent template for implementation
- Agent identity at `/path/to/agents/code-reviewer/AGENT.md` for review via `launch_agent`

**Spawn sequence:**

```
# 1. Create team
TeamCreate(team_name="impl-review", description="Implement then review pipeline")

# 2. Single teammate implements
Task(
  subagent_type="general-purpose",
  team_name="impl-review",
  name="dev",
  prompt="Implement the requested feature. When done, dispatch a code review:

    mcp__nano-agent__launch_agent(
      agentic_prompt='Review all changed files for security, quality, and test coverage',
      agent_path='/path/to/agents/code-reviewer',
      model='YOUR_MODEL',
      provider='YOUR_PROVIDER',
      workspace='/path/to/project'
    )

    Report both the implementation and review results."
)
```

**Flow**: Single teammate implements → dispatches review to external LLM → reports both results.

---

## Pattern 3: Research → Plan → Implement

**When**: Unknown territory — need research before committing to an approach.

**Files needed:**
- `~/.claude/agents/nano-researcher.md`
- `~/.claude/agents/nano-implementer.md`

**Spawn sequence:**

```
# 1. Create team
TeamCreate(team_name="research-impl", description="Research then implement")

# 2. Create phased tasks
TaskCreate(
  subject="Research best approach for feature Y",
  description="Investigate options, trade-offs, and existing patterns in the codebase",
  activeForm="Researching approaches"
)
TaskCreate(
  subject="Plan implementation based on research",
  description="Create implementation plan based on research findings",
  activeForm="Planning implementation"
)
TaskCreate(
  subject="Implement feature Y",
  description="Implement according to the plan",
  activeForm="Implementing feature Y"
)

# 3. Spawn researcher first
Task(
  subagent_type="nano-researcher",
  team_name="research-impl",
  name="researcher",
  prompt="Claim the research task. Investigate the codebase and external resources. Write your findings to docs/research.md. When done, message the lead."
)

# 4. After research, spawn implementer
Task(
  subagent_type="nano-implementer",
  team_name="research-impl",
  name="impl",
  prompt="Read docs/research.md for context. Claim the planning task, write a plan, then claim and execute the implementation task."
)
```

**Flow**: Researcher investigates → writes findings → implementer reads findings → plans → implements.

---

## Choosing a Pattern

| You Need... | Pattern |
|-------------|---------|
| Parallel work with quality review | Pattern 1: Lead + 2 Peers |
| Sequential quality gate | Pattern 2: Implement → Review |
| Exploration before commitment | Pattern 3: Research → Plan → Implement |

## Tips

- **Embed first task in prompt**: When spawning a teammate, include their first task in the `prompt` parameter to avoid an idle-wake cycle.
- **Use `SendMessage` for coordination**: Teammates can't see each other's output unless they message each other or write to shared files.
- **Stateless nano-agents**: Each `prompt_nano_agent` / `launch_agent` call is independent. Pass all context in the prompt or via files in the workspace.
- **Hot-add teammates**: You can spawn new teammates into an existing team at any time with `Task(team_name=...)`.
- **Shutdown gracefully**: Use `SendMessage(type="shutdown_request", recipient="name")` when done.
