# Spec 02: Provider Health Check (check_providers Tool)

## Overview

The `check_providers()` tool enables users to query the health and availability of all 5 configured LLM providers before launching agent work. Currently, users must attempt agent execution to discover if a provider is down, wasting time and tokens on failed calls. This feature introduces a new MCP tool that performs concurrent health checks across OpenAI, Anthropic, Ollama, LM Studio, and Z.ai, returning status, available models, and response latency for each provider.

The implementation builds on existing validation infrastructure in `provider_config.py`, extending it to check all providers in parallel rather than one at a time. Health checks are read-only operations with no side effects — they query provider endpoints or local services to determine availability without consuming tokens or modifying state. This feature unblocks provider fallback chains (US-003) and smart routing (US-005) by providing the availability data they need to make intelligent provider selection decisions.

## Dependencies

### Prerequisites (Must Exist Before Building)
- Python 3.12+ environment with existing nano-agent v1.x codebase
- Existing modules: `constants.py`, `data_types.py`, `provider_config.py`
- `validate_provider_setup_async()` function in `provider_config.py` (lines 241-295)
- `httpx` library already installed (used for async validation)
- Existing `AVAILABLE_MODELS` and `PROVIDER_REQUIREMENTS` constants in `constants.py`

### Unblocked Features (What This Enables)
- **Provider Fallback Chain (US-003)** — Skip known-down providers before attempting execution
- **Smart Model Routing (US-005)** — Route to available providers based on health check data
- **Informed Provider Selection** — Users can check availability before launching long-running tasks

## Design Decisions (from PRD Alignment)

These decisions were explicitly discussed and agreed upon during PRD planning. They are **BINDING** and must be followed exactly:

1. **Separate MCP tool**: `check_providers()` is a new tool, separate from `prompt_nano_agent()` — different tool name, different schema
2. **No input parameters**: Tool takes no parameters (checks all 5 providers unconditionally)
3. **Concurrent checks**: All 5 providers checked in parallel using `asyncio.gather()` with `httpx.AsyncClient`
4. **Reuse existing validation**: Build on `validate_provider_setup_async()` logic but adapt for parallel execution
5. **Health check is read-only**: No side effects, no state changes, no token consumption — just status reporting
6. **Cloud providers (OpenAI, Anthropic, Z.ai)**: Check environment variable is set + endpoint reachable (lightweight ping)
7. **Local providers (Ollama, LM Studio)**: Check service running on localhost + list loaded models via API
8. **Response schema**: Per-provider status (up/down/partial), available models list, response latency in milliseconds
9. **Partial availability handled**: Service up but some models missing returns "partial" status with available subset (local providers only)
10. **Timeout per provider**: 3-second timeout for each provider check (same as existing validation)

## Architecture

### Concurrent Health Check Strategy

The `check_providers()` tool uses `asyncio.gather()` to execute all 5 provider checks in parallel:

```python
async def check_all_providers_async() -> CheckProvidersResponse:
    """Check health of all 5 providers concurrently."""
    tasks = [
        _check_provider_health("openai"),
        _check_provider_health("anthropic"),
        _check_provider_health("ollama"),
        _check_provider_health("lmstudio"),
        _check_provider_health("zai"),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return _assemble_provider_response(results)
```

**Concurrency Model**:
- All 5 checks start simultaneously using `asyncio.gather()`
- Each check has its own 3-second timeout (independent of others)
- Total wait time = max(individual check times), not sum of all checks
- If one check hangs, others complete and return results
- Exceptions caught per-provider (one failure doesn't abort others)

### Provider-Specific Health Check Logic

#### Cloud Providers (OpenAI, Anthropic, Z.ai)

**Health check definition**:
1. **API key check**: Verify required environment variable is set (e.g., `OPENAI_API_KEY`)
2. **Endpoint reachability**: Provider-specific handling:
   - **OpenAI**: Check API key is set → Send authenticated GET to `https://api.openai.com/v1/models` → Parse model list from response
     - If 200: Use real model list from response
     - If 401/403: status="down", error="API key invalid"
     - If connection error: status="down", error="endpoint unreachable"
   - **Anthropic**: Check API key is set → Return static model list from `AVAILABLE_MODELS["anthropic"]` (NO endpoint ping — Anthropic has no models endpoint)
   - **Z.ai**: Check API key is set → Return static model list from `ZAI_AVAILABLE_MODELS` (NO endpoint ping — Z.ai proxies Anthropic protocol, no models endpoint)
3. **Latency measurement**: Time from request start to response end (in milliseconds)

**Status outcomes**:
- **up**: API key set, endpoint reachable (OpenAI only), valid response
- **down**: API key missing OR endpoint unreachable OR invalid response (OpenAI: 401/403/connection error)
- **partial**: NOT applicable for cloud providers (either fully up or down)

#### Local Providers (Ollama, LM Studio)

**Health check definition**:
1. **Service running check**: HTTP connection to localhost endpoint
   - Ollama: `GET http://127.0.0.1:11434/api/tags`
   - LM Studio: `GET http://127.0.0.1:1234/v1/models`
2. **Model listing**: Parse response to extract available model names
3. **Latency measurement**: Time from request start to response end

**Status outcomes**:
- **up**: Service running, responding, all expected models present
- **down**: Service not running (connection refused/timeout) OR no models loaded
- **partial**: Service running but expected models from `AVAILABLE_MODELS` not fully loaded (e.g., Ollama running but `gpt-oss:20b` not pulled)

### Response Schema

The tool returns a structured response with per-provider details:

```python
{
    "success": true,
    "providers": {
        "openai": {
            "status": "up",  # "up" | "down" (cloud providers: no "partial")
            "available_models": ["gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-4o"],
            "latency_ms": 245.3,
            "error": null
        },
        "anthropic": {
            "status": "up",
            "available_models": ["claude-opus-4-1-20250805", "claude-opus-4-20250514", ...],  # Static list from constants
            "latency_ms": 0.5,  # Minimal (key check only)
            "error": null
        },
        "ollama": {
            "status": "partial",  # Service up but not all models loaded
            "available_models": ["gpt-oss:20b", "qwen3-coder:30b"],  # Only 2 of 5 expected
            "latency_ms": 45.2,
            "error": null
        },
        "lmstudio": {
            "status": "down",  # Service not running
            "available_models": [],
            "latency_ms": null,
            "error": "LM Studio service not running. Start with: LM Studio app"
        },
        "zai": {
            "status": "down",  # API key missing
            "available_models": [],
            "latency_ms": null,
            "error": "Missing environment variable: Z_AI_API_KEY"
        }
    },
    "total_check_time_ms": 312.7,  # Max of all individual latencies
    "providers_up": 2,
    "providers_down": 2,
    "providers_partial": 1
}
```

### Tool Comparison

| Aspect | `validate_provider_setup_async()` | `check_providers()` |
|--------|----------------------------------|---------------------|
| **Purpose** | Validate single provider+model combo before execution | Health check all providers (no model specified) |
| **Scope** | One provider, one model | All 5 providers, all models |
| **Execution** | Sequential (one at a time) | Concurrent (all in parallel) |
| **Return** | Tuple (bool, error_message) | Structured dict with status, models, latency |
| **Use Case** | Pre-flight validation before agent execution | Standalone health query for user visibility |
| **Model check** | Validates specific model is available | Lists all available models |
| **Latency tracking** | No | Yes (per-provider in ms) |

### MCP Tool Registration

Following the pattern from `__main__.py` line 41:

```python
# Existing registration
mcp.tool()(prompt_nano_agent)

# New registration (same pattern)
from .modules.nano_agent import check_providers
mcp.tool()(check_providers)
```

**Note**: The `check_providers()` MCP tool function lives in `nano_agent.py` (not `provider_config.py`). It imports and calls `check_all_providers_async()` from `provider_config.py`, following the same pattern as `prompt_nano_agent()` calling `_execute_nano_agent_async()`.

## Implementation Phases

### Phase A: Pydantic Models for Health Check
**Objective**: Define request/response schemas for provider health check

#### Sub-Task A1: Create ProviderHealthStatus model in data_types.py
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/data_types.py`
- **What to implement**:
  - Add new Pydantic model `ProviderHealthStatus` after `PromptNanoAgentResponse` (after line ~60)
  - Fields:
    - `status: Literal["up", "down", "partial"]` (required, description="Provider health status")
    - `available_models: List[str]` (required, default_factory=list, description="List of available model names")
    - `latency_ms: Optional[float]` (optional, default=None, description="Response latency in milliseconds")
    - `error: Optional[str]` (optional, default=None, description="Error message if status is 'down'")
  - Add docstring explaining the model
- **Existing patterns to follow**:
  - Follow `PromptNanoAgentResponse` structure exactly (lines 35-60)
  - Use same Field() parameters: `description`, `default`
  - Use Literal type for status (same as provider in PromptNanoAgentRequest)
- **Acceptance criteria**:
  - `ProviderHealthStatus` model validates correctly
  - `status` must be one of "up", "down", "partial"
  - `available_models` defaults to empty list
  - `latency_ms` and `error` are optional
  - Pydantic validation enforces type constraints

#### Sub-Task A2: Create CheckProvidersResponse model in data_types.py
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/data_types.py`
- **What to implement**:
  - Add new Pydantic model `CheckProvidersResponse` after `ProviderHealthStatus`
  - Fields:
    - `success: bool` (required, description="Whether health checks completed successfully")
    - `providers: Dict[str, ProviderHealthStatus]` (required, description="Health status per provider")
    - `total_check_time_ms: float` (required, description="Total time for all checks in milliseconds")
    - `providers_up: int` (required, default=0, description="Count of providers with status='up'")
    - `providers_down: int` (required, default=0, description="Count of providers with status='down'")
    - `providers_partial: int` (required, default=0, description="Count of providers with status='partial'")
  - Add docstring explaining the model
  - **NO field validator** — counts are computed by caller, no validation needed
- **Existing patterns to follow**:
  - Follow `PromptNanoAgentResponse` structure
  - Use `Dict[str, ProviderHealthStatus]` for providers map
  - Use same Field() description pattern
- **Acceptance criteria**:
  - `CheckProvidersResponse` model validates correctly
  - `providers` dict contains all 5 providers (openai, anthropic, ollama, lmstudio, zai)
  - Count fields (up/down/partial) are plain int with defaults
  - `total_check_time_ms` is positive

### Phase B: Provider Health Check Logic
**Objective**: Implement concurrent health check for all providers

#### Sub-Task B1: Create _check_provider_health helper function
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/provider_config.py`
- **What to implement**:
  - Add `async def _check_provider_health(provider: str) -> ProviderHealthStatus:` function
  - Import `ProviderHealthStatus` from `.data_types`
  - Import `time` for latency measurement
  - Import `httpx` for async HTTP requests
  - Function logic:
    1. Start timer: `start_time = time.perf_counter()`
    2. Handle 3 provider types with simple if/elif branches:
       
       **OpenAI** (cloud with models endpoint):
       - Check `OPENAI_API_KEY` env var is set
       - If missing: return status="down", error="Missing environment variable: OPENAI_API_KEY"
       - Send authenticated GET to `https://api.openai.com/v1/models` with `Authorization: Bearer {api_key}`
       - If 200: Parse model list from `response.json()["data"]`, extract model IDs
       - If 401/403: return status="down", error="API key invalid"
       - If connection error: return status="down", error="endpoint unreachable"
       - Calculate latency, return status="up" with models
       
       **Anthropic/Z.ai** (cloud without models endpoint):
       - Check API key env var is set (`ANTHROPIC_API_KEY` or `Z_AI_API_KEY`)
       - If missing: return status="down", error="Missing environment variable: {key_name}"
       - Return static model list from constants:
         - Anthropic: `AVAILABLE_MODELS["anthropic"]`
         - Z.ai: `ZAI_AVAILABLE_MODELS`
       - Minimal latency (key check only), status="up"
       
       **Ollama/LM Studio** (local providers):
       - Use existing `local_providers` dict from `validate_provider_setup_async()`
       - Send HTTP GET to localhost endpoint with 3-second timeout
       - On success: parse response, extract model list
       - Compare against expected models from `AVAILABLE_MODELS[provider]`
       - If all expected present: status="up"
       - If subset present: status="partial", available_models=actual list
       - If none present or connection error: status="down"
    3. Calculate latency: `latency_ms = (time.perf_counter() - start_time) * 1000`
    4. Return ProviderHealthStatus with appropriate status, models, latency
  - Handle exceptions: httpx.ConnectError, httpx.TimeoutException, Exception
  - Use `logger = logging.getLogger(__name__)` for debug logging
- **Existing patterns to follow**:
  - Follow `validate_provider_setup_async()` structure (lines 241-295)
  - Use same local_providers dict pattern
  - Use same httpx.AsyncClient pattern with timeout=3.0
  - Use same exception handling (ConnectError, TimeoutException)
- **Acceptance criteria**:
  - Function returns ProviderHealthStatus for any valid provider name
  - OpenAI: API key check + authenticated GET /v1/models + handle 200/401/403/connection-error
  - Anthropic/Z.ai: API key check only + return static model list (no endpoint ping)
  - Local providers: service running check + model list + partial status support
  - Latency measured accurately in milliseconds
  - All exceptions caught and returned as status="down" with error message
  - Debug logging for key operations

#### Sub-Task B2: Implement check_all_providers_async orchestrator
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/provider_config.py`
- **What to implement**:
  - Add `async def check_all_providers_async() -> CheckProvidersResponse:` function
  - Import `asyncio` for concurrent execution
  - Import `CheckProvidersResponse` from `.data_types`
  - Function logic:
    1. Start timer: `start_time = time.perf_counter()`
    2. Create list of provider names: `providers = ["openai", "anthropic", "ollama", "lmstudio", "zai"]`
    3. Create tasks: `tasks = [_check_provider_health(p) for p in providers]`
    4. Execute concurrently: `results = await asyncio.gather(*tasks, return_exceptions=True)`
    5. Process results:
       - Initialize `providers_dict = {}`
       - Initialize counters: `up=down=partial=0`
       - For each provider, result pair:
         - If result is Exception: create ProviderHealthStatus(status="down", error=str(result))
         - Else: use result as-is
         - Update counters based on status
         - Add to providers_dict
    6. Calculate total time: `total_check_time_ms = (time.perf_counter() - start_time) * 1000`
    7. Create response: `response = CheckProvidersResponse(success=True, providers=providers_dict, total_check_time_ms=total_check_time_ms, providers_up=up, providers_down=down, providers_partial=partial)`
    8. Return response (not model_dump() — caller handles serialization)
  - Handle top-level exceptions (shouldn't happen, but safe fallback)
  - Log info: `logger.info(f"Health check completed: {up} up, {down} down, {partial} partial in {total_check_time_ms:.1f}ms")`
- **Existing patterns to follow**:
  - Follow async function pattern from `validate_provider_setup_async()`
  - Use asyncio.gather() for concurrent execution (same as existing concurrency tests)
  - Use same logging pattern
  - Return CheckProvidersResponse object (not dict)
- **Acceptance criteria**:
  - Function checks all 5 providers concurrently
  - Total check time is approximately max(individual latencies), not sum
  - Returns CheckProvidersResponse object
  - Counters accurately reflect provider statuses
  - Exceptions in individual checks don't abort other checks
  - Info log emitted with summary

### Phase C: MCP Tool + Registration
**Objective**: Register check_providers as MCP tool and verify integration

#### Sub-Task C1: Implement check_providers MCP tool in nano_agent.py
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/modules/nano_agent.py`
- **What to implement**:
  - Add `async def check_providers(ctx: Context) -> Dict[str, Any]:` function
  - Import `Context` from `mcp.types`
  - Import `check_all_providers_async` from `.provider_config`
  - Function logic:
    1. Report progress: `await ctx.report_progress(0, 1, "Checking provider health...")`
    2. Call orchestrator: `response = await check_all_providers_async()`
    3. Report progress: `await ctx.report_progress(1, 1, "Health check complete")`
    4. Return `response.model_dump()`
  - Add docstring explaining the tool
- **Existing patterns to follow**:
  - Follow `prompt_nano_agent()` pattern (same file)
  - Use same ctx.report_progress() pattern
  - Use same return type (Dict[str, Any] via model_dump())
- **Acceptance criteria**:
  - `check_providers()` function callable as MCP tool
  - Imports `check_all_providers_async()` from provider_config
  - Reports progress via ctx
  - Returns dict matching CheckProvidersResponse schema

#### Sub-Task C2: Register check_providers as MCP tool in __main__.py
- **File to modify**: `apps/nano_agent_mcp_server/src/nano_agent/__main__.py`
- **What to implement**:
  - Import `check_providers` from `.modules.nano_agent` (after line 17, where `prompt_nano_agent` is imported)
  - Register as MCP tool: `mcp.tool()(check_providers)` (after line 41, where `prompt_nano_agent` is registered)
  - Update MCP server instructions docstring to mention all 3 tools
- **Existing patterns to follow**:
  - Follow import pattern from line 17: `from .modules.nano_agent import prompt_nano_agent`
  - Follow registration pattern from line 41: `mcp.tool()(prompt_nano_agent)`
  - Update docstring to match existing style
- **Acceptance criteria**:
  - `check_providers` imported successfully
  - Registered as MCP tool
  - MCP server exposes `prompt_nano_agent`, `launch_agent`, and `check_providers`
  - Docstring updated to mention all 3 tools

### Phase D: Tests
**Objective**: Verify health check logic works correctly

#### Sub-Task D1: Write comprehensive tests
- **File to create**: `apps/nano_agent_mcp_server/tests/test_provider_health.py`
- **What to implement**:
  - `test_check_provider_health_openai_up()` → verify OpenAI up state with valid response (200 OK)
  - `test_check_provider_health_openai_down_invalid_key()` → verify OpenAI down with 401/403
  - `test_check_provider_health_openai_down_unreachable()` → verify OpenAI down with connection error
  - `test_check_provider_health_anthropic_up()` → verify Anthropic up with static list (no endpoint ping)
  - `test_check_provider_health_anthropic_down_missing_key()` → verify Anthropic down with missing key
  - `test_check_provider_health_zai_up()` → verify Z.ai up with static list (no endpoint ping)
  - `test_check_provider_health_zai_down_missing_key()` → verify Z.ai down with missing key
  - `test_check_provider_health_ollama_up()` → verify Ollama up with all models
  - `test_check_provider_health_ollama_partial()` → verify Ollama partial with subset of models
  - `test_check_provider_health_ollama_down()` → verify Ollama down when service not running
  - `test_check_provider_health_lmstudio_up()` → verify LM Studio up
  - `test_check_provider_health_lmstudio_down()` → verify LM Studio down
  - `test_check_all_providers_async_concurrent()` → verify all 5 providers checked concurrently
  - `test_check_all_providers_async_response_schema()` → verify response matches CheckProvidersResponse
  - `test_check_all_providers_async_counters()` → verify up/down/partial counts accurate
  - `test_check_all_providers_async_total_time()` → verify total time is max of individual times
  - `test_check_all_providers_async_one_exception()` → verify one provider exception doesn't abort others
  - `test_check_providers_mcp_tool()` → verify MCP tool calls orchestrator and returns dict
- **Existing patterns to follow**:
  - Follow test structure from `test_agent_identity.py` (US-010)
  - Use `pytest` and `pytest-asyncio` for async tests
  - Use `unittest.mock.AsyncMock` and `patch` for mocking httpx calls
  - Use `tmp_path` fixture for file system tests (if needed)
- **Acceptance criteria**:
  - All tests pass
  - Test coverage >90% for health check logic
  - Edge cases covered (missing keys, 401/403, connection errors, partial availability)
  - Mocked httpx calls avoid hitting real services
  - OpenAI tests verify 200/401/403/connection-error handling
  - Anthropic/Z.ai tests verify static list returned (no endpoint ping)
  - Local provider tests verify partial status support

## Acceptance Criteria

Full checklist from PRD US-002, expanded with technical details:

- [ ] **New MCP tool implemented**: `check_providers()` registered and callable (no parameters)
- [ ] **Response includes provider name**: Each provider keyed by name in response dict
- [ ] **Response includes status (up/down/partial)**: ProviderHealthStatus.status field with "up", "down", or "partial" (partial for local providers only)
- [ ] **Response includes available models list**: ProviderHealthStatus.available_models with actual model names
- [ ] **Response includes latency (ms)**: ProviderHealthStatus.latency_ms with float or null
- [ ] **Reuses existing validation logic**: Builds on `validate_provider_setup_async()` patterns
- [ ] **All 5 providers checked concurrently**: Uses `asyncio.gather()` for parallel execution
- [ ] **OpenAI checked with auth**: API key check + authenticated GET /v1/models + handle 200/401/403/connection-error
- [ ] **Anthropic/Z.ai checked without endpoint**: API key check only + return static model list (no models endpoint)
- [ ] **Local providers checked**: Ollama, LM Studio verify service running + list models + partial status
- [ ] **Registered as MCP tool**: Added to __main__.py alongside prompt_nano_agent and launch_agent
- [ ] **Tests for all provider states**: Up, down, partial model availability covered
- [ ] **Partial availability for local only**: Cloud providers never return "partial" status
- [ ] **Timeout per provider**: 3-second timeout for each provider check
- [ ] **Exceptions isolated**: One provider failure doesn't abort other checks
- [ ] **Total check time accurate**: Reflects max(individual latencies), not sum
- [ ] **No PROVIDER_HEALTH_CHECK_CONFIG**: Simple if/elif branches handle 3 provider types

## Scenarios

### Happy Path

#### Scenario 1: All providers up and available
**Input**:
```python
await check_providers()

# Environment:
# - OPENAI_API_KEY set, OpenAI reachable (200 OK)
# - ANTHROPIC_API_KEY set (key check only)
# - Ollama running on localhost:11434, all models loaded
# - LM Studio running on localhost:1234, models loaded
# - Z_AI_API_KEY set (key check only)
```

**Expected Behavior**:
1. `check_providers()` creates 5 concurrent tasks via `check_all_providers_async()`
2. All 5 health checks execute in parallel
3. Each provider returns status="up" with model list and latency
4. Response assembled with all providers up:
   ```python
   {
       "success": True,
       "providers": {
           "openai": {"status": "up", "available_models": ["gpt-5", "gpt-5-mini", ...], "latency_ms": 245.3, "error": None},
           "anthropic": {"status": "up", "available_models": ["claude-opus-4-1-20250805", ...], "latency_ms": 0.5, "error": None},
           "ollama": {"status": "up", "available_models": ["gpt-oss:20b", ...], "latency_ms": 45.2, "error": None},
           "lmstudio": {"status": "up", "available_models": ["qwen3-coder-next"], "latency_ms": 38.1, "error": None},
           "zai": {"status": "up", "available_models": ["glm-4.7", "glm-4.5-air"], "latency_ms": 0.5, "error": None}
       },
       "total_check_time_ms": 245.3,  # Max of all latencies (OpenAI slowest)
       "providers_up": 5,
       "providers_down": 0,
       "providers_partial": 0
   }
   ```
5. Total check time ~245ms (slowest provider), not ~329ms (sum of all)
6. Info log emitted: "Health check completed: 5 up, 0 down, 0 partial in 245.3ms"

#### Scenario 2: Mixed provider states (up, down, partial)
**Input**:
```python
await check_providers()

# Environment:
# - OPENAI_API_KEY set, OpenAI returns 200 → up
# - ANTHROPIC_API_KEY missing → down
# - Ollama running but only 2 of 5 models loaded → partial
# - LM Studio not running → down
# - Z_AI_API_KEY set → up
```

**Expected Behavior**:
1. All 5 checks execute concurrently
2. OpenAI: status="up", models listed from /v1/models response, latency measured
3. Anthropic: status="down", error="Missing environment variable: ANTHROPIC_API_KEY"
4. Ollama: status="partial", available_models=["gpt-oss:20b", "qwen3-coder:30b"] (only 2 of 5)
5. LM Studio: status="down", error="LM Studio service not running. Start with: LM Studio app"
6. Z.ai: status="up", static model list from ZAI_AVAILABLE_MODELS, minimal latency
7. Response:
   ```python
   {
       "success": True,
       "providers": {
           "openai": {"status": "up", "available_models": [...], "latency_ms": 245.3, "error": None},
           "anthropic": {"status": "down", "available_models": [], "latency_ms": None, "error": "Missing environment variable: ANTHROPIC_API_KEY"},
           "ollama": {"status": "partial", "available_models": ["gpt-oss:20b", "qwen3-coder:30b"], "latency_ms": 45.2, "error": None},
           "lmstudio": {"status": "down", "available_models": [], "latency_ms": None, "error": "LM Studio service not running. Start with: LM Studio app"},
           "zai": {"status": "up", "available_models": ["glm-4.7", "glm-4.5-air"], "latency_ms": 0.5, "error": None}
       },
       "total_check_time_ms": 245.3,
       "providers_up": 2,
       "providers_down": 2,
       "providers_partial": 1
   }
   ```

### Negative Cases

#### Scenario 1: All providers down
**Input**:
```python
await check_providers()

# Environment:
# - All API keys missing
# - Ollama and LM Studio not running
```

**Expected Behavior**:
1. All 5 checks execute concurrently
2. All providers return status="down" with appropriate errors
3. Response:
   ```python
   {
       "success": True,  # Tool succeeded, even though all providers are down
       "providers": {
           "openai": {"status": "down", "available_models": [], "latency_ms": None, "error": "Missing environment variable: OPENAI_API_KEY"},
           "anthropic": {"status": "down", "available_models": [], "latency_ms": None, "error": "Missing environment variable: ANTHROPIC_API_KEY"},
           "ollama": {"status": "down", "available_models": [], "latency_ms": None, "error": "Ollama service not running. Start with: ollama serve"},
           "lmstudio": {"status": "down", "available_models": [], "latency_ms": None, "error": "LM Studio service not running. Start with: LM Studio app"},
           "zai": {"status": "down", "available_models": [], "latency_ms": None, "error": "Missing environment variable: Z_AI_API_KEY"}
       },
       "total_check_time_ms": 2.0,  # Fast failures (missing keys detected immediately)
       "providers_up": 0,
       "providers_down": 5,
       "providers_partial": 0
   }
   ```
4. Tool returns success=True (health check completed, even though all providers are down)

#### Scenario 2: OpenAI returns 401 (invalid API key)
**Input**:
```python
await check_providers()

# Environment:
# - OPENAI_API_KEY set but invalid
# - OpenAI returns 401 Unauthorized
```

**Expected Behavior**:
1. OpenAI check sends authenticated GET to /v1/models
2. Receives HTTP 401
3. Returns status="down" with error="API key invalid"
4. Response:
   ```python
   {
       "openai": {
           "status": "down",
           "available_models": [],
           "latency_ms": 123.4,
           "error": "API key invalid"
       }
   }
   ```

#### Scenario 3: OpenAI connection error
**Input**:
```python
await check_providers()

# Environment:
# - OPENAI_API_KEY set
# - Network unreachable (DNS failure, firewall, etc.)
```

**Expected Behavior**:
1. OpenAI check attempts connection
2. httpx.ConnectError raised
3. Returns status="down" with error="endpoint unreachable"
4. Response:
   ```python
   {
       "openai": {
           "status": "down",
           "available_models": [],
           "latency_ms": None,
           "error": "endpoint unreachable"
       }
   }
   ```

#### Scenario 4: One provider times out, others succeed
**Input**:
```python
await check_providers()

# Environment:
# - OpenAI endpoint hangs (network issue)
# - Other providers respond normally
```

**Expected Behavior**:
1. All 5 checks start concurrently
2. OpenAI check hits 3-second timeout, returns status="down" with timeout error
3. Other 4 providers complete successfully
4. Total check time ~3000ms (timeout duration)
5. Response:
   ```python
   {
       "success": True,
       "providers": {
           "openai": {"status": "down", "available_models": [], "latency_ms": None, "error": "openai endpoint timeout"},
           "anthropic": {"status": "up", ...},
           "ollama": {"status": "up", ...},
           "lmstudio": {"status": "up", ...},
           "zai": {"status": "up", ...}
       },
       "total_check_time_ms": 3000.0,
       "providers_up": 4,
       "providers_down": 1,
       "providers_partial": 0
   }
   ```

### Edge Cases

#### Scenario 1: Local provider returns empty model list
**Input**:
```python
await check_providers()

# Environment:
# - Ollama running but no models loaded (fresh install)
```

**Expected Behavior**:
1. Ollama health check succeeds (service reachable)
2. Model list extracted from response is empty
3. Status determined as "down" (no models available)
4. Response:
   ```python
   {
       "ollama": {
           "status": "down",
           "available_models": [],
           "latency_ms": 42.1,
           "error": None  # No error, but no models either
       }
   }
   ```

#### Scenario 2: Provider returns unexpected response format
**Input**:
```python
await check_providers()

# Environment:
# - OpenAI returns valid HTTP but malformed JSON
```

**Expected Behavior**:
1. OpenAI check receives HTTP 200
2. `response.json()` raises `JSONDecodeError`
3. Exception caught, returns status="down" with error message
4. Response:
   ```python
   {
       "openai": {
           "status": "down",
           "available_models": [],
           "latency_ms": None,
           "error": "Error checking openai: Expecting value: line 1 column 1 (char 0)"
       }
   }
   ```

#### Scenario 3: Concurrent execution with mixed latencies
**Input**:
```python
await check_providers()

# Environment:
# - Ollama: 45ms (fast, local)
# - LM Studio: 38ms (fast, local)
# - Z.ai: 0.5ms (key check only)
# - Anthropic: 0.5ms (key check only)
# - OpenAI: 245ms (slowest, cloud with endpoint ping)
```

**Expected Behavior**:
1. All 5 checks start at same time
2. Ollama completes at 45ms
3. LM Studio completes at 38ms
4. Z.ai completes at 0.5ms
5. Anthropic completes at 0.5ms
6. OpenAI completes at 245ms
7. `asyncio.gather()` returns when all complete
8. Total check time = 245ms (max of all latencies)
9. Response includes individual latencies for each provider

## Test Plan

### Unit Tests (test_provider_health.py)

| Test Function | Verifies | Key Assertions |
|---------------|----------|----------------|
| `test_check_provider_health_openai_up()` | OpenAI up state with 200 response | Asserts status="up", models list non-empty, latency_ms > 0, error is None |
| `test_check_provider_health_openai_down_invalid_key()` | OpenAI down with 401/403 | Asserts status="down", error contains "API key invalid", latency_ms measured |
| `test_check_provider_health_openai_down_unreachable()` | OpenAI down with connection error | Asserts status="down", error contains "endpoint unreachable", latency_ms is None |
| `test_check_provider_health_openai_timeout()` | OpenAI timeout handling | Asserts status="down", error contains "timeout", latency_ms is None |
| `test_check_provider_health_anthropic_up()` | Anthropic up with static list | Asserts status="up", models from AVAILABLE_MODELS["anthropic"], minimal latency, no endpoint ping |
| `test_check_provider_health_anthropic_down_missing_key()` | Anthropic down with missing key | Asserts status="down", error about missing key, no endpoint ping attempted |
| `test_check_provider_health_zai_up()` | Z.ai up with static list | Asserts status="up", models from ZAI_AVAILABLE_MODELS, minimal latency, no endpoint ping |
| `test_check_provider_health_zai_down_missing_key()` | Z.ai down with missing key | Asserts status="down", error about missing key, no endpoint ping attempted |
| `test_check_provider_health_ollama_up()` | Ollama up with all models | Asserts status="up", models list includes all expected models |
| `test_check_provider_health_ollama_partial()` | Ollama partial with subset of models | Asserts status="partial", available_models is subset of expected |
| `test_check_provider_health_ollama_down()` | Ollama down when service not running | Asserts status="down", error contains "service not running", includes startup hint |
| `test_check_provider_health_ollama_empty_models()` | Ollama down with no models loaded | Asserts status="down", available_models is empty list |
| `test_check_provider_health_lmstudio_up()` | LM Studio up state | Asserts status="up", models list non-empty |
| `test_check_provider_health_lmstudio_down()` | LM Studio down when service not running | Asserts status="down", error contains "service not running" |
| `test_check_all_providers_async_concurrent()` | Concurrent execution of all 5 providers | Asserts all 5 providers checked, total time < sum of individual times |
| `test_check_all_providers_async_response_schema()` | Response matches CheckProvidersResponse | Asserts response object has all required fields, types match |
| `test_check_all_providers_async_counters()` | Up/down/partial counters accurate | Asserts providers_up + providers_down + providers_partial = 5, counts match actual statuses |
| `test_check_all_providers_async_total_time()` | Total time is max of individual times | Asserts total_check_time_ms >= max(individual latencies), total_check_time_ms < sum(latencies) |
| `test_check_all_providers_async_one_exception()` | One provider exception doesn't abort others | Asserts 4 providers succeed, 1 fails with error, response still complete |
| `test_check_all_providers_async_all_down()` | All providers down scenario | Asserts providers_down=5, all have status="down", success=True (check succeeded) |
| `test_check_providers_mcp_tool()` | MCP tool calls orchestrator | Asserts check_providers() calls check_all_providers_async(), returns dict via model_dump() |

### Integration Tests

| Test Function | Verifies | Key Assertions |
|---------------|----------|----------------|
| `test_check_providers_mcp_tool_registered()` | Tool registered on MCP server | Asserts "check_providers" in tool list, callable without parameters |
| `test_check_providers_real_ollama()` | Real Ollama service (if running) | Asserts actual Ollama health check works, marks test as xfail if service not running |
| `test_check_providers_real_lmstudio()` | Real LM Studio service (if running) | Asserts actual LM Studio health check works, marks test as xfail if service not running |
| `test_check_providers_no_api_keys()` | Behavior with no API keys set | Asserts all cloud providers down with missing key errors, local providers checked normally |

## Files to Create/Modify

### New Files to Create

| File Path | Purpose | Key Content |
|-----------|---------|-------------|
| `apps/nano_agent_mcp_server/tests/test_provider_health.py` | Unit tests for health check | All unit tests for provider health check logic |

### Existing Files to Modify

| File Path | Changes | Lines Affected |
|-----------|---------|----------------|
| `apps/nano_agent_mcp_server/src/nano_agent/modules/data_types.py` | Add `ProviderHealthStatus` and `CheckProvidersResponse` models | Add after line ~60 (after `PromptNanoAgentResponse`) |
| `apps/nano_agent_mcp_server/src/nano_agent/modules/provider_config.py` | Add `_check_provider_health()` and `check_all_providers_async()` | Add after line ~295 (after `validate_provider_setup_async`) |
| `apps/nano_agent_mcp_server/src/nano_agent/modules/nano_agent.py` | Add `check_providers()` MCP tool | Add after `prompt_nano_agent()` function |
| `apps/nano_agent_mcp_server/src/nano_agent/__main__.py` | Import and register `check_providers` | Add import after line 17, add registration after line 41, update docstring |

## Migration / Backward Compatibility

### Zero-Impact Guarantee

This feature is **100% backward compatible**. Existing users experience no breaking changes:

1. **`prompt_nano_agent()` unchanged**:
   - Zero modifications to existing function
   - Same signature, same behavior, same response schema
   - Existing calls work exactly as before

2. **`launch_agent()` unchanged**:
   - Zero modifications to existing function
   - Same signature, same behavior
   - Existing calls work exactly as before

3. **New tool is additive only**:
   - `check_providers()` is a separate MCP tool
   - Users who don't call it are unaffected
   - No changes to existing infrastructure

4. **No configuration changes**:
   - No new config files
   - No environment variables (reuses existing API keys)
   - No database or state changes

### Migration Path for Users Who Want Provider Health

Users who want to check provider health before launching agents can opt-in:

1. **Call health check before agent execution**:
   ```python
   # Check which providers are available
   health = await check_providers()
   
   # Choose an available provider
   if health["providers"]["openai"]["status"] == "up":
       provider = "openai"
   elif health["providers"]["ollama"]["status"] == "up":
       provider = "ollama"
   else:
       raise Exception("No providers available")
   
   # Launch agent with chosen provider
   result = await prompt_nano_agent(
       "Build a REST API",
       provider=provider,
       model="gpt-5-mini"
   )
   ```

2. **Use health check for monitoring**:
   ```python
   # Periodic health checks
   health = await check_providers()
   for provider_name, status in health["providers"].items():
       if status["status"] != "up":
           print(f"Warning: {provider_name} is {status['status']}: {status.get('error', 'Unknown')}")
   ```

### Rollback Plan

If issues arise, the feature can be disabled:

1. **Unregister MCP tool** (comment out 1 line in `__main__.py`):
   ```python
   # mcp.tool()(check_providers)  # Temporarily disabled
   ```

2. **No data loss or migration needed**:
   - No existing configuration modified
   - No database or state changes
   - Health check is read-only (no side effects)

## Example Usage

### Example 1: Check all providers before launching agent

```python
from nano_agent import check_providers, prompt_nano_agent

# Check which providers are available
health = await check_providers()

print(f"Providers up: {health['providers_up']}/5")
print(f"Total check time: {health['total_check_time_ms']:.1f}ms")

# Find an available provider
available_providers = [
    name for name, status in health["providers"].items()
    if status["status"] == "up"
]

if not available_providers:
    print("No providers available!")
else:
    # Use the first available provider
    provider = available_providers[0]
    print(f"Using {provider}")
    
    result = await prompt_nano_agent(
        "Build a REST API for user management",
        provider=provider,
        model=health["providers"][provider]["available_models"][0]
    )
```

### Example 2: Display provider health in a table

```python
from tabulate import tabulate

health = await check_providers()

# Build table rows
rows = []
for provider, status in health["providers"].items():
    latency = f"{status['latency_ms']:.1f}ms" if status['latency_ms'] else "N/A"
    models = len(status['available_models'])
    error = status['error'] or ""
    rows.append([provider, status['status'], models, latency, error])

# Print table
print(tabulate(rows, headers=["Provider", "Status", "Models", "Latency", "Error"]))

# Output:
# Provider    Status    Models    Latency    Error
# ----------  --------  --------  ---------  ---------------------------------
# openai      up              4    245.3ms
# anthropic   down            0    N/A        Missing environment variable: ANTHROPIC_API_KEY
# ollama      partial         2    45.2ms
# lmstudio    down            0    N/A        LM Studio service not running. Start with: LM Studio app
# zai         up              2    0.5ms
```

### Example 3: Use health check for provider fallback (pre-US-003)

```python
health = await check_providers()

# Define preferred provider order
preferred_providers = ["zai", "openai", "anthropic", "ollama", "lmstudio"]

# Find first available provider
chosen_provider = None
for provider in preferred_providers:
    if health["providers"][provider]["status"] == "up":
        chosen_provider = provider
        break

if chosen_provider:
    print(f"Using {chosen_provider}")
    result = await prompt_nano_agent(
        "Implement feature X",
        provider=chosen_provider
    )
else:
    print("No providers available!")
```

### Example 4: Monitor provider latency over time

```python
import time
from datetime import datetime

# Track latency over multiple checks
latency_history = []

for i in range(5):
    health = await check_providers()
    
    timestamp = datetime.now().isoformat()
    for provider, status in health["providers"].items():
        if status["latency_ms"]:
            latency_history.append({
                "timestamp": timestamp,
                "provider": provider,
                "latency_ms": status["latency_ms"]
            })
    
    print(f"Check {i+1}: {health['providers_up']} up, {health['total_check_time_ms']:.1f}ms")
    time.sleep(10)  # Wait 10 seconds between checks

# Analyze latency trends
for provider in ["openai", "anthropic", "ollama", "lmstudio", "zai"]:
    provider_latencies = [
        entry["latency_ms"] 
        for entry in latency_history 
        if entry["provider"] == provider
    ]
    if provider_latencies:
        avg_latency = sum(provider_latencies) / len(provider_latencies)
        print(f"{provider}: {avg_latency:.1f}ms average")
```

---

**End of Spec 02: Provider Health Check (check_providers Tool) - Round 2 Revision**
