# Recipe 01: MCP Direct Dispatch

Dispatch a self-contained task to a specific external LLM using `prompt_nano_agent`. Best for single-round tasks where you control the model selection.

## Use Case

Use this when:
- You need a specific external LLM (not YOUR_MODEL)
- The task is self-contained (no multi-turn needed)
- You want direct control over model/provider
- Cost transparency is important

## Steps

### 1. Check Available Providers

First, verify which providers/models are available:

```python
# In your MCP client or CLI
!check_providers()
```

Expected output shows available models like `openai/gpt-4o`, `anthropic/claude-3-5-sonnet`, etc.

### 2. Dispatch with Detailed Prompt

Use `prompt_nano_agent` with explicit instructions and YOUR_MODEL/YOUR_PROVIDER:

```python
response = prompt_nano_agent(
    model="YOUR_MODEL",  # e.g., "openai/gpt-4o" or "anthropic/claude-3-5-sonnet"
    provider="YOUR_PROVIDER",  # e.g., "openai" or "anthropic"
    prompt="""
You are a senior Python developer. Analyze the following code file and identify:
1. Any security vulnerabilities
2. Performance optimization opportunities
3. Code style issues per PEP 8

File to analyze: src/utils/helper.py

Return a structured report with:
- List of vulnerabilities (high/medium/critical)
- Performance suggestions with reasoning
- Style corrections
""",
    context={
        "file_path": "/path/to/your/file.py",
        "additional_instructions": "Focus on security first"
    }
)
```

### 3. Verify Output

Check the response structure:

```python
if response.status == "success":
    print(response.content)
else:
    print(f"Error: {response.error}")
```

## Example: Implement Utility Function

**Scenario**: You need a utility function implemented in TypeScript.

```python
result = prompt_nano_agent(
    model="openai/gpt-4o",
    provider="openai",
    prompt="""
Implement a TypeScript utility function for debouncing:

Function signature: 
```typescript
function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): T
```

Requirements:
1. Use setTimeout and clearTimeout
2. Support leading/trailing edge execution
3. Return cancel function to prevent invocation
4. Include JSDoc comments

Place in: src/utils/debounce.ts
""",
    context={
        "target_file": "src/utils/debounce.ts",
        "existing_code": None
    }
)
```

## Example: Analyze File

**Scenario**: Review a Python file for best practices.

```python
analysis = prompt_nano_agent(
    model="anthropic/claude-3-5-sonnet",
    provider="anthropic",
    prompt="""
Review this Python file for:
1. Type safety issues (missing type hints)
2. Error handling gaps
3. Potential bugs

File content:
{file_content}

Return your findings in this format:
## Issues Found
- [Critical/Warning/Info] Issue description

## Suggested Fixes
1. Fix for issue 1
2. Fix for issue 2
""",
    context={
        "file_content": open("src/main.py").read()
    }
)
```

## Important Notes

- **Cost**: Free for local models, pay-per-token for cloud providers
- **Latency**: Single roundtrip = fastest option
- **No Context Persistence**: Each call is independent; embed all needed context in prompt
- **Model Selection**: Always specify both `model` and `provider` explicitly

## When NOT to Use This Recipe

- For multi-turn conversations → use Teammate or launch_agent
- For consistent agent identity across tasks → use launch_agent with AGENT.md
- For background processing → use Background Bash or Background Agent
