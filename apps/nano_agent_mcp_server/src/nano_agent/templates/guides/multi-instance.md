# Multi-Instance Guide

How to run multiple agents or teammates without naming collisions.

## Rules

1. **Filenames must be unique** — two agent files with the same filename in the same directory will collide.
2. **The `name:` field (YAML frontmatter) must be unique per agent** — Claude Code uses this field to identify subagents, not the filename.
3. **Agent identities (AGENT.md) have no naming constraint** — they live in separate directories and are referenced by path.

## Naming Convention

```
nano-{role}-{differentiator}.md
```

Examples:
- `nano-reviewer-fast.md` (uses a fast local model)
- `nano-reviewer-deep.md` (uses a powerful cloud model)
- `nano-implementer-backend.md` (backend specialist)
- `nano-implementer-frontend.md` (frontend specialist)

## Example: 3 Teammates from the Same Template

Start with the `nano-teammate.md` template and create 3 variants:

### 1. Create Agent Files

```bash
# Copy template 3 times with different names
cp nano-teammate.md ~/.claude/agents/nano-dev.md
cp nano-teammate.md ~/.claude/agents/nano-qa.md
cp nano-teammate.md ~/.claude/agents/nano-devops.md
```

### 2. Edit Each File

In each file, change the YAML frontmatter `name:` field and the model/provider:

**nano-dev.md:**
```yaml
---
name: nano-dev
description: Development teammate
model: YOUR_MODEL
provider: YOUR_PROVIDER
---
```

**nano-qa.md:**
```yaml
---
name: nano-qa
description: QA/testing teammate
model: YOUR_MODEL
provider: YOUR_PROVIDER
---
```

**nano-devops.md:**
```yaml
---
name: nano-devops
description: DevOps teammate
model: YOUR_MODEL
provider: YOUR_PROVIDER
---
```

### 3. Spawn as a Team

```
TeamCreate(team_name="project-x", description="Full-stack team")

Task(
  subagent_type="nano-dev",
  team_name="project-x",
  name="dev",
  prompt="You are the developer. Claim implementation tasks from the task list."
)

Task(
  subagent_type="nano-qa",
  team_name="project-x",
  name="qa",
  prompt="You are QA. Write tests and review implementation quality."
)

Task(
  subagent_type="nano-devops",
  team_name="project-x",
  name="devops",
  prompt="You are DevOps. Handle CI/CD, Docker, and deployment tasks."
)
```

## What Causes Collisions

| Situation | Collision? | Fix |
|-----------|-----------|-----|
| Same filename, different directories | No | Each directory is independent |
| Same filename, same directory | Yes | Rename the file |
| Same `name:` in frontmatter, different files | Yes | Change the `name:` field |
| Same agent identity (AGENT.md) used by two `launch_agent` calls | No | Each call is independent |
| Same `name` parameter in two `Task()` calls for the same team | Yes | Use different names |

## Tips

- Always change `name:` in YAML frontmatter when duplicating agent templates
- Use descriptive differentiators: role, provider, speed tier, or domain
- Agent identities (for `launch_agent`) don't need unique names — they're referenced by path
- Team member names (the `name` parameter in `Task()`) must be unique within a team
