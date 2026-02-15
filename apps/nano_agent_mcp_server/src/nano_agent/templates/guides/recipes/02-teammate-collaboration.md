# Recipe 02: Teammate Collaboration

Create a multi-agent team with a lead agent coordinating peer agents. Best for complex tasks requiring specialized expertise and multiple rounds of collaboration.

## Use Case

Use this when:
- Multiple AI agents need to collaborate on a task
- Different specializations are required (e.g., architect + implementer + reviewer)
- Rich back-and-forth conversation is needed
- You want Claude Code's native team coordination

## Key Concepts

- **TeamCreate**: Creates a team with a shared task list
- **Task (subagent)**: Spawns a teammate that joins the team
- **SendMessage**: Sends messages between teammates
- **TaskCreate/TaskUpdate**: Coordinates work via shared task list
- **Nano-agent MCP tools**: Dispatches work to external LLMs from within teammates

## Steps

### 1. Create the Team

```
TeamCreate(
  team_name="feature-impl",
  description="Implement and review the user management API"
)
```

This creates a team with a shared task list. You (the lead) coordinate the work.

### 2. Create Tasks for the Team

```
TaskCreate(
  subject="Design user management API architecture",
  description="Define endpoints, data models, and error handling strategy for the user management API",
  activeForm="Designing API architecture"
)

TaskCreate(
  subject="Implement user management API",
  description="Implement the endpoints based on the architecture design",
  activeForm="Implementing API"
)

TaskCreate(
  subject="Review implementation for security and quality",
  description="Review the implemented code for security vulnerabilities, error handling, and code quality",
  activeForm="Reviewing implementation"
)
```

### 3. Spawn Teammates

Spawn teammates using the `Task` tool with a `team_name`. Each teammate is a Claude Code subagent:

```
Task(
  subagent_type="general-purpose",
  team_name="feature-impl",
  name="architect",
  prompt="You are the system architect. Check the task list, claim your task, and design the API architecture."
)

Task(
  subagent_type="general-purpose",
  team_name="feature-impl",
  name="implementer",
  prompt="You are the implementer. Check the task list, claim your task once the architecture is ready, and implement the API."
)
```

### 4. Teammates Dispatch to External LLMs

Inside a teammate, dispatch coding work to an external LLM via nano-agent:

```
mcp__nano-agent__prompt_nano_agent(
  agentic_prompt="Implement the user CRUD endpoints in src/api/users.py following FastAPI patterns.
    Read the architecture doc at docs/architecture.md first.",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace="/path/to/project"
)
```

### 5. Coordinate via Messages

Teammates communicate using `SendMessage`:

```
SendMessage(
  type="message",
  recipient="implementer",
  content="Architecture is ready at docs/architecture.md. You can start implementation now.",
  summary="Architecture design complete"
)
```

### 6. Review and Iterate

The reviewer teammate can dispatch a review to an external LLM:

```
mcp__nano-agent__launch_agent(
  agentic_prompt="Review all Python files in src/api/ for security issues and code quality",
  agent_path="/path/to/code-reviewer",
  model="YOUR_MODEL",
  provider="YOUR_PROVIDER",
  workspace="/path/to/project"
)
```

### 7. Mark Tasks Complete and Shut Down

```
TaskUpdate(taskId="3", status="completed")

SendMessage(
  type="shutdown_request",
  recipient="architect",
  content="All work complete, shutting down"
)
```

## Example: Implement + Review Pipeline

**Scenario**: One teammate implements, another reviews.

```
# 1. Create team
TeamCreate(team_name="impl-review", description="Implement then review")

# 2. Create tasks
TaskCreate(subject="Implement auth middleware", description="...", activeForm="Implementing")
TaskCreate(subject="Review auth middleware", description="...", activeForm="Reviewing")

# 3. Spawn teammates
Task(
  subagent_type="general-purpose",
  team_name="impl-review",
  name="dev",
  prompt="Claim the implementation task. Use mcp__nano-agent__prompt_nano_agent to dispatch coding work to YOUR_MODEL on YOUR_PROVIDER."
)

Task(
  subagent_type="general-purpose",
  team_name="impl-review",
  name="reviewer",
  prompt="Wait for the implementation task to complete, then claim the review task. Use mcp__nano-agent__launch_agent with a code-reviewer identity."
)
```

## Important Notes

- **Cost**: Teammates use Claude Code (paid); nano-agent dispatch cost depends on target model
- **Latency**: Higher due to multiple agents and coordination overhead
- **Team lifecycle**: Teams exist for the session unless deleted with `TeamDelete`
- **Stateless nano-agents**: Each `prompt_nano_agent` / `launch_agent` call is independent — pass all context in the prompt or via files

## When NOT to Use This Recipe

- For simple single-round tasks → use `prompt_nano_agent` directly (Recipe 01)
- For consistent agent identity without team overhead → use `launch_agent` (Recipe 04)
- For shell commands without AI → use Background Bash (Recipe 03)
