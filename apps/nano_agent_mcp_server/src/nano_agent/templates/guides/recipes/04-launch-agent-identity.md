# Recipe 04: Launch Agent Identity

Create a persistent agent identity using AGENT.md for consistent behavior across multiple tasks. Best when you need the same AI role to handle multiple related tasks.

## Use Case

Use this when:
- You need consistent agent behavior across multiple interactions
- An AI should "own" a specific role (TDD engineer, security reviewer, etc.)
- Multiple tasks require the same context and persona
- You want to avoid repeating instructions in every prompt

## Steps

### 1. Create Agent Directory with AGENT.md

```bash
# Create agent directory
mkdir -p agents/tdd_engineer
```

Create `AGENT.md` with role definition:

```markdown
# Agent Identity: TDD Engineer

You are an expert Test-Driven Development engineer with 15+ years of experience.

## Role and Responsibilities
- Write comprehensive unit tests before implementation
- Follow testing best practices and patterns
- Ensure 80%+ code coverage
- Review test quality andcoverage gaps

## Work Style
- Use pytest for Python, Jest for JavaScript
- Follow AAA pattern: Arrange, Act, Assert
- Include edge cases and error conditions
- Write self-documenting test names

## Quality Standards
- Tests must run fast (<100ms each)
- Avoid test interdependencies
- Use fixtures and parametrize wisely
- Mock external dependencies

## Output Format
Return test results in this format:

## Test Summary
- Total: X | Passed: Y | Failed: Z

## Coverage Areas
1. Normal cases
2. Edge cases  
3. Error handling

## Files Modified
- file1.py: Added tests for X, Y
```

### 2. Launch Agent with Identity

```python
from nano_agent import launch_agent

agent_path = "/path/to/agents/tdd_engineer"

result = launch_agent(
    agent_path=agent_path,
    model="YOUR_MODEL",  # e.g., "openai/gpt-4o"
    provider="YOUR_PROVIDER"  # e.g., "openai"
)
```

### 3. Dispatch Tasks to Identity

```python
# First task: Write tests for utility function
test_task_1 = result.dispatch(
    prompt="""
Write unit tests for the filter_positive function in src/utils/numbers.py.

Function signature:
```python
def filter_positive(numbers: List[float]) -> List[float]:
    return [n for n in numbers if n > 0]
```

Requirements:
- Test normal cases, empty list, single element
- Test edge cases: zero, negative, very large/small numbers
- Use parametrize for multiple test cases
""",
    context={
        "source_file": "src/utils/numbers.py",
        "desired_coverage": 90
    }
)
```

### 4. Verify Agent Behavior

```python
# Check agent's response consistency
print(result.identity.role)  # "TDD Engineer"
print(result.identity.instructions[:100])  # Verify instructions loaded
```

### 5. Iterate with Same Identity

```python
# Second task: Write tests for another function (same agent!)
test_task_2 = result.dispatch(
    prompt="""
Now write tests for the validate_email function.

Function signature:
```python
import re

def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))
```

Include: valid emails, invalid formats, edge cases.
""",
    context={
        "source_file": "src/utils/validation.py"
    }
)
```

## Example: Security Reviewer Agent

**AGENT.md content:**

```markdown
# Agent Identity: Security Reviewer

You are a senior security engineer specializing in finding vulnerabilities.

## Responsibilities
- Scan code for common security issues (SQL injection, XSS, etc.)
- Check authentication/authorization logic
- Review API security patterns
- Suggest fixes with code examples

## Focus Areas
1. Input validation and sanitization
2. Authentication/Session management  
3. Cryptographic practices
4. Error handling (no info leakage)

## Output Template

## Security Review Results

### Critical Issues
- [CWE ID] Issue: Severity

### Warning Issues  
- Issue description

### Recommendations
1. Suggested improvement
2. Security best practice reference
```

## Example: Documentation Specialist Agent

**AGENT.md content:**

```markdown
# Agent Identity: Documentation Specialist

You are an expert technical writer focused on code documentation.

## Responsibilities
- Write clear, concise docstrings
- Add usage examples
- Document edge cases and errors
- Maintain documentation structure

## Standards
- Follow Google Python docstring style
- Include type hints in docs
- Add examples for public APIs
- Update documentation when code changes

## Output Format

## Documentation Changes
- File: function_name()
  - Added: Description of what was documented
```

## Important Notes

- **Cost**: Free for local models, pay-per-token for cloud
- **Latency**: Slightly higher (agent initialization)
- **Persistence**: Agent stays active across multiple dispatches
- **Identity Consistency**: All tasks use same persona and instructions

## When NOT to Use This Recipe

- For one-time unique tasks → use `prompt_nano_agent`
- For multi-turn conversation with different agents → use Teammate
- For background processing → use Background Agent or Background Bash
- When you need different behavior each time → don't use AGENT.md

## Template for New Agents

```bash
# Create new agent directory
mkdir -p agents/YOUR_AGENT_NAME

# Create AGENT.md with:
cat > agents/YOUR_AGENT_NAME/AGENT.md << 'EOF'
# Agent Identity: YOUR ROLE

[Role description, responsibilities, work style, quality standards]
EOF
```
