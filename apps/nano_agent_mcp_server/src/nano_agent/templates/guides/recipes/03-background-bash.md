# Recipe 03: Background Bash

Run long-running shell commands without blocking your workflow. Use `run_in_background=true` to execute build, test, or data processing tasks while continuing other work.

## Use Case

Use this when:
- Running test suites (pytest, Jest, RSpec, etc.)
- Building Docker images or application binaries
- Processing large datasets
- Running migrations or data transformation jobs
- Any task that takes longer than a few seconds

## Steps

### 1. Execute Background Command

Use `Bash` with `run_in_background=true`:

```python
result = Bash(
    command="pytest tests/ -v --tb=short",
    run_in_background=True
)
```

### 2. Continue Working

The command runs in the background; you can proceed with other tasks:

```python
# This doesn't wait for pytest to finish!
print("Tests started in background, continuing with implementation...")

# Implement next feature while tests run
new_feature_code = """
def process_data(data: list) -> dict:
    # Your implementation here
    return {"processed": len(data)}
"""
```

### 3. Check Output Later

Use `TaskOutput` to check results:

```python
# At any point, check on the background task
output = TaskOutput(task_id=result.task_id)

if output.status == "running":
    print("Tests still running...")
elif output.status == "completed":
    print(output.stdout)
    if output.return_code != 0:
        print(f"Tests failed with exit code: {output.return_code}")
elif output.status == "failed":
    print(f"Task failed: {output.error}")
```

## Example: Run Full Test Suite

**Scenario**: Start tests, implement a new feature, then check results.

```python
# Step 1: Start background test run
test_result = Bash(
    command="cd /project && npm test",
    working_dir="/path/to/project",
    run_in_background=True
)

# Step 2: Continue with implementation
feature_implementation = """
// New feature implementation
export function validateUser(user) {
    return user.email && user.password;
}
"""

# Step 3: Check back on tests
output = TaskOutput(task_id=test_result.task_id)

if output.status == "completed" and output.return_code == 0:
    print("✅ All tests passed! Feature is safe to merge.")
else:
    print(f"Test status: {output.status}")
    if output.stdout:
        print("Recent output:", output.stdout[-500:])  # Last 500 chars
```

## Example: Build Docker Image

```python
build_result = Bash(
    command="docker build -t myapp:latest .",
    working_dir="./docker",
    run_in_background=True
)

# While building, write deployment docs
deployment_docs = """
## Deployment

1. Build image: `docker build -t myapp:latest .`
2. Run container: `docker run -p 8080:80 myapp:latest`
"""

# Later, check build status
output = TaskOutput(task_id=build_result.task_id)
if output.status == "completed":
    if output.return_code == 0:
        print("Image built successfully!")
        # Proceed with deployment
    else:
        print(f"Build failed: {output.stderr}")
```

## Example: Data Processing Pipeline

```python
# Start data processing
processing = Bash(
    command="python scripts/process_data.py --input data/raw.csv --output data/processed.csv",
    run_in_background=True
)

# While processing, write analysis code
analysis_code = """
import pandas as pd

df = pd.read_csv("data/processed.csv")
print(df.describe())
"""

# Wait for completion (or check periodically)
import time
time.sleep(30)  # Give it time

output = TaskOutput(task_id=processing.task_id)
if output.status == "completed":
    print("Data processing complete!")
```

## Important Notes

- **Cost**: Free - no LLM tokens used
- **Latency**: Depends on command; non-blocking execution
- **No AI Reasoning**: This is pure shell execution, no LLM involved
- **Task ID**: Always get a unique `task_id` for tracking

## Getting Command Output

```python
# Immediate output (if available)
print(output.stdout)  # Standard output
print(output.stderr)  # Standard error  
print(output.return_code)  # Exit code (0 = success)

# Streaming output (for very long commands)
if hasattr(output, 'stream'):
    for line in output.stream():
        print(line)  # Real-time streaming
```

## Error Handling

```python
output = TaskOutput(task_id=task_id)

if output.status == "completed":
    if output.return_code == 0:
        print("✅ Success")
        print(output.stdout)
    else:
        print(f"❌ Failed with code {output.return_code}")
        print("Stderr:", output.stderr)
elif output.status == "failed":
    print(f"Task failed to execute: {output.error}")
```

## When NOT to Use This Recipe

- For AI-powered tasks → use `prompt_nano_agent`, Teammate, or Subagent
- For quick commands (<1 second) → use synchronous Bash without background
- When you need LLM integration → use Background Agent instead
