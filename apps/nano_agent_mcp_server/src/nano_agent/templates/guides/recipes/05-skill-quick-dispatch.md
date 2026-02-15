# Recipe 05: Skill Quick Dispatch

Quickly dispatch tasks via slash commands. Create reusable skills for frequent patterns like "review this function" or "analyze this error". Ideal when you want to invoke common AI tasks with a single command.

## Use Case

Use this when:
- You frequently dispatch the same type of task
- You want a one-click solution for common AI operations
- You need to share dispatch patterns with your team
- You want convenience over full control

## Steps

### 1. Create Skill Template

```bash
# Navigate to skills directory (usually in project root)
mkdir -p .nano-agent/skills

# Create skill file
touch .nano-agent/skills/review_function.md
```

### 2. Customize SKILL.md

Create `SKILL.md` with template:

```markdown
# Skill: Review Function

**Description**: Analyze a code function for issues and improvements.

**Model**: YOUR_MODEL
**Provider**: YOUR_PROVIDER

## Instructions to AI
You are a senior code reviewer. Review the provided function for:
1. Security vulnerabilities
2. Performance issues  
3. Code quality
4. Edge cases

## Input Format
```
<function_code>
```

## Output Format
### Issues Found
- [Severity] Issue: Description

### Suggested Fixes
1. Fix description

### Overall Rating
A+/B/C/D/F
```

### 3. Install the Skill

```bash
# If using CLI
nano-agent skill install ./.nano-agent/skills/review_function.md

# Or reference directly via path
```

### 4. Invoke Skill via Slash Command

```markdown
/nano-dispatch review_function "Please review this function for security issues"

Function:
```
def authenticate_user(username, password):
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    return execute_query(query)
```
```

The AI will respond using your skill's instructions and model.

## Example: Error Analyzer Skill

**SKILL.md content:**

```markdown
# Skill: Analyze Error

**Description**: Analyze error messages and suggest fixes.

**Model**: YOUR_MODEL
**Provider**: YOUR_PROVIDER

## Instructions to AI
You are an expert debugging assistant. Given an error, identify:
1. Root cause
2. Likely triggers
3. Concrete fix steps

## Input Format
Error message:
```
<error_output>
```

Code context (optional):
```
<code_snippet>
```

## Output Format
### Root Cause
[Explanation]

### How to Reproduce
[Steps]

### Fix Steps
1. First action
2. Second action

### Code Example
```language
<fixed_code>
```
```

## Example: Test Generator Skill

**SKILL.md content:**

```markdown
# Skill: Generate Tests

**Description**: Create comprehensive unit tests for a function.

**Model**: YOUR_MODEL  
**Provider**: YOUR_PROVIDER

## Instructions to AI
You are a test-driven development expert. Generate tests that:
1. Cover normal, edge, and error cases
2. Use parametrize for multiple inputs
3. Include assertions for side effects

## Input Format
Function:
```
<function_code>
```

Testing framework: <framework_name>

## Output Format
```python
# Test file content
import pytest

<test_code_here>
```
```

## Example: Code Documentation Skill

**SKILL.md content:**

```markdown
# Skill: Document Function  

**Description**: Add comprehensive docstrings to functions.

**Model**: YOUR_MODEL
**Provider**: YOUR_PROVIDER

## Instructions to AI
Add docstrings following Google Python style. Include:
- Brief description
- Args section with types
- Returns section
- Raises section (if applicable)

## Input Format
Function to document:
```
<function_code>
```

## Output Format
Only return the function with docstring added:
```python
<function_with_docstring>
```
```

## Important Notes

- **Cost**: Depends on underlying model (free for local)
- **Latency**: Fast - no setup overhead
- **Reusability**: Skills can be shared across team members
- **Customization**: Each skill uses YOUR_MODEL/YOUR_PROVIDER

## Multiple Skills Workflow

```bash
# List installed skills
nano-agent skill list

# Update a skill
nano-agent skill update review_function

# Remove a skill  
nano-agent skill remove old_skill
```

## When NOT to Use This Recipe

- For one-time unique tasks with no reuse potential → use `prompt_nano_agent` directly
- When you need full control over context → manual dispatch is better
- For complex multi-step workflows → use Teammate or launch_agent

## Template for New Skills

```markdown
# Skill: YOUR_SKILL_NAME

**Description**: SHORT_DESCRIPTION

**Model**: YOUR_MODEL  
**Provider**: YOUR_PROVIDER

## Instructions to AI
[Your AI instructions here]

## Input Format
[How users provide input]

## Output Format
[Expected output structure]
```
