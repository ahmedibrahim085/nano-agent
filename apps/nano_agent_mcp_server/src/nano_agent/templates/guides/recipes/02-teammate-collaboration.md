# Recipe 02: Teammate Collaboration

Create a multi-agent team with a lead agent coordinating peer agents. Best for complex tasks requiring specialized expertise and multiple rounds of collaboration.

## Use Case

Use this when:
- Multiple AI agents need to collaborate on a task
- Different specializations are required (e.g., architect + implementer + reviewer)
- Rich back-and-forth conversation is needed
- You want Claude Code's native subagent support

## Steps

### 1. Create Team with Lead Agent

```python
from nano_agent import create_team

# Define team roles and expertise
team = create_team(
    name="feature_implementation",
    description="Lead agent coordinating implementation and review",
    members=[
        {
            "name": "architect",
            "role": "System Architect",
            "instructions": "Design system architecture and component interactions"
        },
        {
            "name": "implementer",
            "role": "Senior Developer",
            "instructions": "Implement code following architectural guidelines"
        },
        {
            "name": "reviewer",
            "role": "Code Reviewer",
            "instructions": "Review code for quality, security, and maintainability"
        }
    ]
)
```

### 2. Spawn Teammates with Specialized Instructions

Use the `Task` tool to spawn teammates with specific goals:

```python
# Spawn architect
architect_task = Task(
    team_name="feature_implementation",
    agent_name="architect",
    goal="Design the architecture for the new feature",
    context={
        "requirements": "Build a REST API for user management",
        "constraints": ["Use async/await", "Support pagination"]
    }
)

# Spawn implementer
implementer_task = Task(
    team_name="feature_implementation",
    agent_name="implementer",
    goal="Implement the user management API",
    context={
        "architecture": architect_task.result,
        "framework": "fastapi"
    }
)
```

### 3. Dispatch to External LLM

Each teammate can use YOUR_MODEL/YOUR_PROVIDER:

```python
# Lead agent coordinates and can dispatch to external models
result = lead_agent.dispatch(
    model="YOUR_MODEL",
    provider="YOUR_PROVIDER",
    prompt="""
You are the lead architect. Review the implementer's code and:
1. Check alignment with architecture
2. Identify potential issues
3. Suggest improvements

Return:
- Approval status (approve/reject/revise)
- Specific feedback items
- Estimated effort for any requested changes
""",
    context={
        "code": implementer_task.result,
        "architecture_doc": architecture_result
    }
)
```

### 4. Review and Iterate

Collect results and iterate:

```python
# Reviewer analyzes all work
review = Task(
    team_name="feature_implementation",
    agent_name="reviewer",
    goal="Final review of all deliverables",
    context={
        "code": implementer_task.result,
        "feedback": result.content
    }
)

if review.status == "approve":
    print("Implementation approved!")
else:
    # Send back to implementer
    Task(
        team_name="feature_implementation",
        agent_name="implementer",
        goal="Address review feedback",
        context={
            "feedback": review.content,
            "current_code": implementer_task.result
        }
    )
```

### 5. Finalize with SendMessage

Use `SendMessage` to communicate team results:

```python
from nano_agent import SendMessage

SendMessage(
    receiver="user",
    content=f"""
## Implementation Complete

- Architecture: {architecture_result}
- Code: {implementer_task.result}
- Review Status: {review.status}
""",
    attachments={
        "architectural_design": architecture_doc,
        "source_code": implementer_task.result_file
    }
)
```

## Example: Multi-Model Team

**Scenario**: Compare different LLM approaches and select best one.

```python
# Lead agent with specialized teammates
team = create_team(
    name="llm_comparison",
    description="Compare different LLM approaches for task"
)

# Spawn teammates to different models
model_a = Task(
    team_name="llm_comparison",
    agent_name="gpt4_analyst",
    model="openai/gpt-4o",
    provider="openai",
    goal="Analyze task requirements using GPT-4"
)

model_b = Task(
    team_name="llm_comparison",
    agent_name="claude_analyst", 
    model="anthropic/claude-3-5-sonnet",
    provider="anthropic",
    goal="Analyze task requirements using Claude 3.5 Sonnet"
)

# Lead compares results
comparison = lead.dispatch(
    model="openai/gpt-4o",
    provider="openai",
    prompt="""
Compare these two analyses and recommend:
1. Which model performed better for this task?
2. Why did it perform better?
3. Recommended approach for production
"""
)
```

## Important Notes

- **Cost**: Teammate tasks use Claude Code, which is paid
- **Latency**: Higher due to multiple agents and turns
- **Context Sharing**: Teammates can access shared context from lead
- **Team Persistence**: Teams exist for the session unless deleted

## When NOT to Use This Recipe

- For simple single-round tasks → use `prompt_nano_agent`
- For background processing → use Background Agent
- For quick one-off tasks → use Subagent (Task tool)
- When you only need one agent → launch_agent is simpler

## Template for New Teams

```python
# Copy and customize this template
create_team(
    name="YOUR_TEAM_NAME",
    description="YOUR_TEAM_DESCRIPTION",
    members=[
        {
            "name": "role_name",
            "role": "Agent Role Title",
            "instructions": "Specific instructions for this agent"
        }
    ]
)
```
