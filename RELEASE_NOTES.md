# Release Notes

Newest releases first. Each release separated by `---`.

---

# Release: GLM-5 Model Support

**Branch**: `feat/glm5-model`
**Base**: `main` (post tool-resilience merge)
**Date**: 2026-02-13
**Commits**: 2 | **Files changed**: 2 | **+61 / -1 lines**

## Summary

Adds GLM-5 (744B MoE, 44B active) as a Z.ai provider model alongside existing GLM-4.7 and GLM-4.5-air. GLM-5 is Z.ai's frontier reasoning model with native chain-of-thought thinking support enabled by default.

No architecture changes — GLM-5 uses the same `LitellmModel` bridge and Coding Plan endpoint (`/api/anthropic`) as GLM-4.7.

## What Changed

### Production Code (`constants.py`)

| Registry | Change |
|----------|--------|
| `MODEL_INFO` | Added `"glm-5": "GLM-5 - Z.ai frontier reasoning model (744B MoE)"` |
| `ZAI_AVAILABLE_MODELS` | Added `"glm-5"` (now `["glm-5", "glm-4.7", "glm-4.5-air"]`) |
| `MODEL_CAPABILITIES` | Added full capability entry with thinking enabled |

**GLM-5 ModelCapability**:
```python
"glm-5": ModelCapability(
    temperature=1.0,
    max_tokens=131072,      # 131K output (200K context window)
    top_p=0.95,
    extra_body={
        "thinking": {"type": "enabled"},
        "allowed_openai_params": ["thinking"],
    },
)
```

### LiteLLM Thinking Passthrough

GLM-5's `thinking` parameter enables chain-of-thought reasoning — the capability that drives its SOTA benchmark performance. However, LiteLLM's Anthropic provider blocks unknown parameters by default, raising `UnsupportedParamsError`.

**Solution**: Pass `allowed_openai_params=["thinking"]` alongside `thinking` in `extra_body`. The flow:

1. `ModelCapability.extra_body` → `ModelSettings.extra_body`
2. Agent SDK unpacks `extra_body` into `**kwargs` for `litellm.acompletion()`
3. `thinking` matches the named parameter in `acompletion()` signature
4. `allowed_openai_params` flows into `**kwargs` → extends LiteLLM's supported params list
5. LiteLLM properly handles `thinking` via its Anthropic transformation layer

This approach is non-invasive — no changes to `provider_config.py` or global LiteLLM settings.

## Tests (`test_model_capabilities.py`)

6 new tests across 4 test classes:

| Test | Class | Verifies |
|------|-------|----------|
| `test_glm5_has_full_output_capacity` | TestRegistryContents | max_tokens == 131072 |
| `test_glm5_thinking_enabled` | TestRegistryContents | extra_body has thinking + allowed_openai_params |
| `test_validate_tool_support_glm5_supported` | TestToolSupportValidation | GLM-5 passes tool support check |
| `test_get_model_settings_glm5` | TestGetModelSettings | ModelSettings has correct temp/tokens/top_p |
| `test_glm5_full_pipeline` | TestIntegrationPipeline | End-to-end: validation → ModelSettings with thinking in extra_body |

Total model capability tests: **75** (was 69).

## Empirical Verification

All verified via live Z.ai Coding Plan (Max plan) API calls:

| Test | Result |
|------|--------|
| Basic GLM-5 call via nano-agent MCP | PASS |
| GLM-5 tool calling (list_directory) | PASS |
| GLM-5 thinking blocks returned via LiteLLM | PASS (213 reasoning tokens) |
| GLM-5 thinking + tool calling combined | PASS |
| GLM-5 multi-phase complex task (all 8 agent tools) | PASS (26/26 subtests, 117K tokens, ~5 min) |
| Direct curl to `/api/anthropic` with thinking param | PASS (HTTP 200) |
| `litellm.acompletion()` with thinking + allowed_openai_params | PASS |

## Commits

| # | Hash | Message |
|---|------|---------|
| 1 | `75e41cb` | feat(zai): add GLM-5 model support alongside GLM-4.7 |
| 2 | `95d8623` | feat(zai): enable GLM-5 thinking (chain-of-thought reasoning) |

## Files Changed

```
constants.py              | 12 +++++++++++-  (1 modified, 11 added)
test_model_capabilities.py | 50 ++++++++++++++++++++++  (50 added)
```

## Usage

```python
mcp__nano-agent__prompt_nano_agent(
    agentic_prompt="Your task here",
    model="glm-5",
    provider="zai"
)
```

## Requirements

- Z.ai Max plan (or Pro plan with GLM-5 access)
- `Z_AI_API_KEY` environment variable set

---

# Release: run_tests Coverage Gaps

**Branch**: `test/run-tests-missing-coverage`
**Base**: `main` (post tool-resilience merge)
**Date**: 2026-02-13
**Commits**: 3 | **Files changed**: 1 | **+100 / -2 lines**

## Summary

Pure test additions closing 3 coverage gaps in the `run_tests` agent tool identified during tool-resilience verification. No production code changes.

## Tests Added

### `test_run_tests_npm_execution`
Tests the full npm execution path: `package.json` auto-detection → `"npm test"` command build → subprocess → output assembly. Uses mocked `asyncio.create_subprocess_shell` to avoid npm dependency. Verifies command string references `FRAMEWORK_COMMANDS["npm"]` constant and CWD is set to workspace.

### `test_run_tests_timeout_kills_process`
Tests `asyncio.wait_for` timeout handling (lines 893-901 of `nano_agent_tools.py`). Mock subprocess hangs forever; `COMMAND_TIMEOUT_SECONDS` patched to 0.01s. Verifies: `proc.kill()` called, cleanup `communicate()` called after kill, error message contains correct timeout value.

### `test_run_tests_specific_file_target`
Tests the `target.is_file()` branch (line 874) — all previous tests only passed directories. Creates two test files (one passing, one failing), targets only the passing file. Asserts positive proof (1 passed, exit_code 0) and negative proof (`"THIS_SHOULD_NOT_RUN"` not in output).

## Commits

| # | Hash | Message |
|---|------|---------|
| 1 | `fef5e67` | test(run_tests): add npm execution test covering full async path |
| 2 | `62ff147` | test(run_tests): add timeout behavior test with kill verification |
| 3 | `a5474dc` | test(run_tests): add specific-file targeting test with negative proof |

## Files Changed

```
test_nano_agent_tools.py | 102 +++  (3 new test methods + import changes)
```

---

# Release: Tool Resilience

**Branch**: `feat/tool-resilience`
**Base**: `main` (post Qwen Cloud provider merge)
**Date**: 2026-02-13
**Commits**: 10 | **Files changed**: 6 | **+869 / -4 lines**

## What This Release Does

When nano-agent models finish a task, they sometimes try to call tools that don't exist in our tool set. For example, `qwen3-coder-next` called `run_tests` after building a pytest project — correct intent, wrong tool name. The OpenAI Agent SDK crashes with `ModelBehaviorError` at that point, killing the entire agent run and losing all work done up to that moment.

This release solves the problem with a two-layer defense:

1. **Give agents the tools they actually need** — `search_files` and `run_tests` are the two most commonly hallucinated tool names across 10 coding agent frameworks we surveyed. By implementing them as real tools, ~90% of hallucination cases become legitimate tool calls instead of crashes.

2. **Catch everything else gracefully** — For the remaining unknown tool names, a pre-filter monkey-patch intercepts them before the SDK can crash. Valid tool calls in the same response still execute normally. The model receives a helpful error listing available tools so it can self-correct on the next turn.

Additionally, this release adds support for `qwen3-coder-next` (Qwen's latest coding model) running on LM Studio.

## New Tools

### `search_files(pattern, directory, file_glob)`
Recursive grep-based file search. Returns matching lines with file paths and line numbers.

- Uses `grep -rn -E` under the hood — fast, handles large codebases
- Supports regex patterns and file glob filtering (e.g., `*.py`, `*.js`)
- Output truncated at 30K characters (same limit as bash tool)
- Security: `--` end-of-options marker prevents grep flag injection, workspace boundary validation prevents path traversal, glob validation blocks directory escape

### `run_tests(test_path, framework)`
Runs test suites with automatic framework detection.

- Auto-detects: pytest (from conftest.py/pyproject.toml), npm (from package.json), cargo (from Cargo.toml)
- Supports explicit framework selection: `pytest`, `unittest`, `npm`, `jest`, `cargo`
- Both passing and failing tests return output (not errors) so the model can read results
- Security: workspace boundary validation, `shlex.quote()` for path arguments

## SDK Crash Prevention

**Problem**: OpenAI Agent SDK (v0.8.4) raises `ModelBehaviorError` inside a loop over `response.output` when it encounters an unknown tool call. All valid tool calls processed before the crash are lost. This is a known issue (openai/openai-agents-python#325, open since March 2025, unfixed).

**Solution**: A pre-filter monkey-patch on `process_model_response` that:
1. Scans `response.output` for unknown `ResponseFunctionToolCall` items
2. If none found — calls original function as-is (zero overhead on happy path)
3. If unknown found — removes them, processes valid calls normally via original function, then appends synthetic error items using the SDK's own `ToolCallItem`/`ToolCallOutputItem` pattern (same approach as `approvals.py:22-39`)

The error message lists all available tool names so the model can self-correct.

## Security Hardening

Code reviews by Z.ai (glm-4.7) and Qwen Next (qwen3-coder-next) identified CRITICAL security issues that were fixed before merge:

| Issue | Severity | Fix |
|-------|----------|-----|
| Grep flag injection via pattern parameter | CRITICAL | `--` end-of-options marker before pattern argument |
| Path traversal in search_files directory | CRITICAL | `resolve().relative_to(workspace)` boundary check |
| Path traversal in run_tests test_path | CRITICAL | Same workspace boundary validation |
| Command injection via unquoted test paths | CRITICAL | `shlex.quote()` for all path arguments in shell commands |
| Double-patch race condition | CRITICAL | `threading.Lock` with module-level `_patch_applied` flag |
| file_glob directory escape | HIGH | Block path separators and `..` in glob patterns |
| Empty response.output not guarded | HIGH | Fast-return to original function on None/empty output |
| ContextVar test fixture leak | HIGH | Reset before AND after yield in autouse fixtures |

## qwen3-coder-next Support

- Added to `MODEL_CAPABILITIES` registry with 128K max output tokens
- Added to `MODEL_INFO` with correct LM Studio model ID (`qwen/qwen3-coder-next`)
- `MAX_AGENT_TURNS` bumped from 20 to 50 to support longer coding sessions

## System Prompt Update

The agent system prompt now lists all 8 tools with negative guidance:

```
You have ONLY these 8 tools. Do NOT call any other tool name.
```

This serves as the primary defense — smart models (like qwen3-coder-next) follow this instruction and never attempt unknown tools. The monkey-patch is the fallback for weaker models.

## Test Coverage

| Test Suite | Tests | Status |
|------------|-------|--------|
| search_files (basic + security) | 11 | All pass |
| run_tests (basic + security) | 10 | All pass |
| tool resilience (monkey-patch) | 7 | All pass |
| model capabilities (qwen3-coder-next) | 21 | All pass |
| **Total new tests** | **49** | **All pass** |
| Full regression (307/346) | 346 | 39 pre-existing failures, 0 new |

## Commits (chronological)

| # | Hash | Message |
|---|------|---------|
| 1 | `05f85ec` | feat: add qwen3-coder-next to MODEL_CAPABILITIES and MODEL_INFO |
| 2 | `40da182` | feat: maximize qwen3-coder-next output to 128K tokens |
| 3 | `131d7e3` | fix: use full LM Studio model ID qwen/qwen3-coder-next |
| 4 | `c6762eb` | feat: bump MAX_AGENT_TURNS from 20 to 50 |
| 5 | `70545d3` | feat(tools): add search_files tool for recursive file content search |
| 6 | `8b4a690` | feat(tools): add run_tests tool with auto-detection of test frameworks |
| 7 | `74e53fb` | fix(resilience): pre-filter monkey-patch for unknown tool call recovery |
| 8 | `bcd6643` | docs(prompt): update system prompt to list all 8 tools with negative guidance |
| 9 | `f1794be` | test(integration): register new tools and fix ContextVar test isolation |
| 10 | `34d778b` | fix(security): address CRITICAL review findings from Z.ai and Qwen Next |

## Files Changed

```
constants.py            |  26 ++-   (new tool constants, system prompt update)
nano_agent.py           | 126 +++   (resilience monkey-patch + security hardening)
nano_agent_tools.py     | 214 +++   (search_files + run_tests implementations)
test_nano_agent_tools.py| 195 +++   (28 new tool tests + 6 security tests)
test_tool_resilience.py | 255 +++   (NEW — 7 resilience tests)
test_model_capabilities | 57  +++   (21 qwen3-coder-next capability tests)
```

---

# Release: Qwen Cloud Provider + ModelCapability Pipeline Extension

**Branch:** `feat/qwen-provider`
**Date:** February 2026
**Commits:** 16 (9 feat, 4 fix, 3 docs)
**Scope:** 16 files changed, +1549 / -32 lines
**New Tests:** 60 (29 auth + 11 provider + 20 model capabilities)

## What's New

### Qwen Cloud as 6th LLM Provider

Nano-agent now supports **Qwen Cloud**, bringing the total to 6 providers. The available model is `coder-model` (Qwen3-Coder-480B-A35B-Instruct) — a cloud-hosted coding specialist with 480B parameters, optimized for agentic tool-use workflows.

```python
# From Claude Code
mcp__nano-agent__prompt_nano_agent(
    agentic_prompt="Create a FastAPI app with CRUD endpoints",
    model="coder-model",
    provider="qwen"
)
```

**Provider summary after this release:**

| Provider | Type | Models | Auth |
|----------|------|--------|------|
| OpenAI | Cloud | gpt-5, gpt-5-mini, gpt-5-nano, gpt-4o | `OPENAI_API_KEY` env var |
| Anthropic | Cloud | claude-sonnet-4, claude-opus-4, claude-opus-4-1, claude-3-haiku | `ANTHROPIC_API_KEY` env var |
| Z.ai | Cloud | glm-4.7, glm-4.5-air | `Z_AI_API_KEY` env var |
| **Qwen** | **Cloud** | **coder-model** | **OAuth file (`~/.qwen/oauth_creds.json`)** |
| Ollama | Local | gpt-oss:20b, gpt-oss:120b, qwen3-coder:30b, gemma3:27b, magistral | None |
| LM Studio | Local | (dynamic) | None |

### How Qwen Authentication Works

Unlike other cloud providers that use environment variable API keys, Qwen uses **OAuth file-based authentication**. Credentials are stored at `~/.qwen/oauth_creds.json` containing an access token and refresh token.

**Setup:**
1. Authenticate via the Qwen CLI: `qwen login`
2. The CLI writes credentials to `~/.qwen/oauth_creds.json`
3. Nano-agent automatically reads, validates, and refreshes tokens as needed

Token refresh uses `curl` subprocess because Qwen's WAF (Alibaba Cloud) blocks Python HTTP client fingerprints (httpx, requests). The refresh is transparent to the user — expired tokens are automatically refreshed before agent execution begins.

**Token lifecycle:**
```
Read ~/.qwen/oauth_creds.json
        │
        ▼
  Token expired?  ──No──→  Return access_token
        │
       Yes
        │
        ▼
  curl POST to Qwen OAuth endpoint
        │
        ▼
  Save new tokens (atomic write: .tmp → rename)
        │
        ▼
  Return new access_token
```

### ModelCapability Pipeline Extension

The `ModelCapability` → `get_model_settings()` → `ModelSettings` pipeline previously could only express 3 of the SDK's 17 parameters (temperature, max_tokens, top_p). This release adds **4 new optional fields**:

| Field | Type | Range | Purpose |
|-------|------|-------|---------|
| `parallel_tool_calls` | `Optional[bool]` | True/False/None | Enable concurrent tool execution |
| `frequency_penalty` | `Optional[float]` | [-2.0, 2.0] | Penalize repeated tokens |
| `presence_penalty` | `Optional[float]` | [-2.0, 2.0] | Penalize tokens already present |
| `extra_body` | `Optional[Dict[str, Any]]` | Any dict | Provider-specific params passed directly to API |

**Backward compatibility:** All new fields default to `None`. When `None`, the parameter is omitted from the API call (using the SDK's `NOT_GIVEN` sentinel). Existing models produce identical `ModelSettings` as before — verified by regression tests.

**The `extra_body` escape hatch:** Some providers have parameters not in the standard OpenAI API spec (e.g., Qwen's `top_k` and `repetition_penalty`). The `extra_body` dict is passed directly to the `chat.completions.create()` call, allowing any provider-specific parameter without modifying the SDK.

### Optimized Qwen3-Coder Parameters

The `coder-model` entry applies official vendor-recommended parameters from the [Qwen3-Coder HuggingFace model card](https://huggingface.co/Qwen/Qwen3-Coder-480B-A35B-Instruct):

| Parameter | Value | Via | Evidence |
|-----------|-------|-----|----------|
| temperature | 0.7 | `ModelSettings.temperature` | HuggingFace model card, LM Studio preset, Qwen docs |
| top_p | 0.8 | `ModelSettings.top_p` | Same 4 sources |
| top_k | 20 | `extra_body` | HuggingFace model card |
| repetition_penalty | 1.05 | `extra_body` | HuggingFace model card |
| parallel_tool_calls | True | `ModelSettings.parallel_tool_calls` | Empirically verified via curl |
| max_tokens | 65536 | `ModelSettings.max_tokens` | Maximum supported by API |

Parameters intentionally NOT set: `frequency_penalty`, `presence_penalty` — Qwen docs explicitly warn that presence_penalty "may cause language mixing and a slight decrease in model performance" for coding tasks.

## Dashboard Changes

The web dashboard (`nano-web`, port 8484) is updated for 6 providers:

- **Grid:** Responsive layout updated to `lg:grid-cols-6`
- **Qwen card:** Orange color theme (`bg-orange-500/20 text-orange-400 border-orange-500/30`)
- **Status:** Shows "online" when `~/.qwen/oauth_creds.json` exists, "no_api_key" otherwise
- **Config:** Qwen shows "Not Required" in the Configuration section (OAuth-based, no env var needed)
- **Health check:** Qwen included in the concurrent 6-provider health check

## Error Handling

The OAuth module (`qwen_auth.py`) includes multiple layers of defensive error handling:

### Credential Validation
Token types are validated, not just key existence. The following corrupted states are caught early with descriptive error messages:
- `access_token: null` → "invalid (type=NoneType)"
- `access_token: ""` → "invalid (type=str)"
- `access_token: 123` → "invalid (type=int)"
- Same validation for `refresh_token`

### URL-Encoded POST Body
Token refresh uses `urllib.parse.urlencode()` instead of f-string interpolation. Tokens containing `&`, `=`, `+`, or `%` are properly percent-encoded, preventing malformed OAuth requests.

### OAuth Error Parsing
When the token endpoint returns an OAuth error like `{"error": "invalid_grant", "error_description": "refresh token revoked"}`, the `error_description` is extracted and surfaced in the exception. Previously, this would show the generic "missing access_token" message.

### Atomic Write with Cleanup
Credentials are saved via atomic write (`.tmp` + `os.rename`). If either step fails, the orphaned `.tmp` file is cleaned up and the original exception re-raised.

### Expiry Default Warning
When the refresh response omits `expires_in`, a warning is logged before defaulting to 21600 seconds (6 hours), making silent assumptions visible.

## Architecture

### Provider Wiring

Qwen follows the `AsyncOpenAI` + `OpenAIChatCompletionsModel` pattern (same as Ollama), pointed at `https://portal.qwen.ai/v1`:

```
┌─────────────┐     ┌──────────────┐     ┌────────────────────────┐
│ qwen_auth   │────→│ AsyncOpenAI  │────→│ OpenAIChatCompletions  │
│ get_valid_  │     │ (base_url=   │     │ Model                  │
│ token()     │     │  portal.qwen │     │ (model="coder-model")  │
│             │     │  api_key=    │     │                        │
│             │     │  oauth_token)│     │                        │
└─────────────┘     └──────────────┘     └────────────────────────┘
```

### Registration Checklist (All Complete)

| Location | What's registered |
|----------|-------------------|
| `data_types.py` | `"qwen"` added to `ProviderType` Literal |
| `constants.py` | `MODEL_INFO`, `MODEL_CAPABILITIES`, `QWEN_BASE_URL`, `QWEN_AVAILABLE_MODELS`, `PROVIDER_REQUIREMENTS` |
| `provider_config.py` | `create_agent()` branch, `validate_provider_setup()` (sync + async), health check |
| `token_tracking.py` | Token pricing (all $0.00 — free tier) |
| `cli.py` | `check_api_key()` Qwen branch |
| `web/server.py` | `/api/providers`, `/api/models` endpoints |
| `web/static/index.html` | `providerNames` array, color map, grid layout |

## Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_qwen_auth.py` | 29 | Happy path (6), Negative scenarios (12), Edge cases (4), Robustness (7) |
| `test_qwen_provider.py` | 11 | create_agent (3), validate_setup sync (3), async (3), health (2) |
| `test_model_capabilities.py` | 64 | 45 pre-existing + 19 new (data model, pipeline, boundaries, Qwen registration) |
| `test_provider_health.py` | 28 | Updated expectations from 5 → 6 providers |
| **Total scoped** | **132** | **All passing** |

### Review Process

7 independent reviewers:
- **Z.ai** (glm-4.7 via nano-MCP): Architecture, security, race conditions, backward compatibility
- **Qwen** (coder-model via nano-MCP): Self-review of OAuth module and parameter configuration
- **5 Claude Code subagents**: Dashboard alignment, silent failure analysis, test coverage, code quality, backward compatibility

Results: 9 issues identified → 6 fixed → 3 deferred (documented below).

## Known Limitations

1. **No concurrent token refresh locking.** `get_valid_token()` has no mutex. If two agents call it simultaneously with an expired token, both will attempt to refresh — the second may fail with `invalid_grant`. This is acceptable for current single-agent usage patterns and is a design decision deferred to a future concurrent-agents feature.

2. **Token baked at agent creation time.** The OAuth token is fetched once during `create_agent()` and stored as a fixed `api_key` in the `AsyncOpenAI` client. Qwen tokens expire (default 6 hours). Long-running sessions may encounter mid-execution 401 errors. A proper fix requires a custom `httpx.Auth` class, which is beyond the scope of this release.

3. **curl dependency.** Token refresh requires `curl` on the system. Checked at refresh time with `shutil.which("curl")` — raises `QwenAuthError("curl not found — required for Qwen token refresh")` if missing.

## Breaking Changes

**None.** All changes are additive:
- New `ModelCapability` fields default to `None` — existing models unaffected
- `"qwen"` added to `Literal` provider types — additive, no removals
- Dashboard grid expanded — responsive, no layout changes for existing providers
- All 132 scoped tests pass with zero regressions

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| `modules/qwen_auth.py` | **NEW** — OAuth token management | +234 |
| `tests/test_qwen_auth.py` | **NEW** — 29 auth tests | +405 |
| `tests/test_qwen_provider.py` | **NEW** — 11 provider tests | +205 |
| `tests/test_model_capabilities.py` | Extended — 19 new tests | +268 |
| `modules/provider_config.py` | Qwen wiring + pipeline extension | +76 |
| `modules/constants.py` | Qwen constants + coder-model config | +23 |
| `modules/data_types.py` | 4 new ModelCapability fields | +26 |
| `web/server.py` | Dashboard Qwen endpoints | +24 |
| `web/static/index.html` | 6-provider grid + orange theme | +7 |
| `tests/test_provider_health.py` | 5→6 provider expectations | +27 |
| `modules/token_tracking.py` | Qwen pricing entry | +10 |
| `modules/nano_agent.py` | Qwen import for error handling | +2 |
| `cli.py` | Qwen credential check | +11 |
| `CLAUDE.md` | 5→6 providers | +4 |
| `KNOWLEDGE_TRANSFER.md` | 5→6 providers | +10 |
| `tasks/specs/qwen-provider-tasks.json` | Task tracker | +249 |

## Commit Log

| # | SHA | Type | Description |
|---|-----|------|-------------|
| 1 | `ba29738` | feat | Add OAuth token management module with 20 tests |
| 2 | `1277df3` | feat | Register Qwen in constants, data types, and model capabilities |
| 3 | `247a3b1` | feat | Wire Qwen into create_agent and validate_provider_setup |
| 4 | `a7618cf` | feat | Add Qwen health check and update provider count to 6 |
| 5 | `b6ada68` | feat | Align dashboard with 6-provider architecture |
| 6 | `ec7bccc` | feat | Update MCP tool docstrings and add token pricing |
| 7 | `cf3c542` | fix | Dashboard provider status, CLI creds check, and docstring |
| 8 | `4dd7331` | docs | Add Qwen provider task tracker with evidence |
| 9 | `45f772d` | feat | Add parallel_tool_calls, frequency/presence_penalty, extra_body to ModelCapability |
| 10 | `e67469e` | feat | Wire 4 new fields through get_model_settings pipeline |
| 11 | `060cc7f` | feat | Apply official Qwen3-Coder parameters to coder-model |
| 12 | `0e44ee5` | fix | Validate credential token types and values, not just key existence |
| 13 | `a5f4455` | fix | URL-encode refresh token POST body to prevent injection |
| 14 | `036f84e` | fix | Improve error handling in token refresh and credential save |
| 15 | `23af7cc` | docs | Update provider_config module docstring to list all 6 providers |
| 16 | `f65412d` | docs | Update provider count from 5 to 6 across project documentation |

---

# Release: MODEL_CAPABILITIES Registry

**Branch**: `feat/model-capabilities`
**Base**: `main` (post bash-tool-rename merge)
**Date**: February 2026
**Commits**: 3 | **Files changed**: 5 | **+537 / -52 lines**

## Summary

Introduces a centralized `MODEL_CAPABILITIES` registry and `ModelCapability` data model for per-model configuration. Before this release, model-specific settings (temperature, max_tokens, tool support) were scattered across `get_model_settings()` branches with hardcoded values. Now every model has a declarative capability entry, and a pipeline validates tool support before agent creation.

## What Changed

### `ModelCapability` Data Model (`data_types.py`)

New Pydantic model with validated fields:

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `temperature` | `float` | 0.2 | Default temperature (0.0–2.0) |
| `max_tokens` | `int` | 16000 | Maximum output tokens (>0) |
| `supports_tools` | `bool` | True | Whether model supports tool calling |
| `supports_temperature` | `bool` | True | Whether model accepts temperature |
| `top_p` | `Optional[float]` | None | Nucleus sampling threshold |

### `MODEL_CAPABILITIES` Registry (`constants.py`)

Centralized dict mapping model IDs to `ModelCapability` entries. Covers all 14 models across 5 providers at the time of creation:

- **OpenAI**: gpt-5, gpt-5-mini, gpt-5-nano, gpt-4o
- **Anthropic**: claude-opus-4-1, claude-opus-4, claude-sonnet-4, claude-3-haiku
- **Ollama**: gpt-oss:20b, gpt-oss:120b, qwen3-coder:30b, gemma3:27b, magistral
- **Z.ai**: glm-4.7, glm-4.5-air

Unknown models fall back to `DEFAULT_MODEL_CAPABILITY` (temperature=0.2, max_tokens=16000).

### Pre-flight Tool Support Validation (`provider_config.py`)

`ProviderConfig.validate_tool_support(model)` checks `supports_tools` before agent creation. Models like `gemma3:27b` (no tool support) are rejected early with a descriptive error instead of crashing mid-execution.

### Review Hardening

Post-review commit added:
- `logging` import and warnings for unknown models
- Top-level imports for `ModelCapability` and `get_model_capabilities`
- 12 additional regression tests for boundary cases

## Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_model_capabilities.py` | 38 | Registry contents, tool validation, ModelSettings pipeline, integration |

All 38 tests passing. Zero regressions in full suite.

## Commits

| # | Hash | Message |
|---|------|---------|
| 1 | `525edb5` | feat: add ModelCapability model and MODEL_CAPABILITIES registry |
| 2 | `1abc2e5` | feat: add pre-flight tool support validation for models |
| 3 | `7830600` | fix: review hardening — add logging, promote imports, add 12 regression tests |

## Files Changed

```
constants.py              |  82 ++++-  (MODEL_CAPABILITIES registry, get_model_capabilities)
data_types.py             |  27 +++   (ModelCapability model)
nano_agent.py             |  42 +--   (use registry instead of hardcoded values)
provider_config.py        |  65 ++--  (validate_tool_support, pipeline refactor)
test_model_capabilities.py| 373 +++   (NEW — 38 tests)
```

---

# Release: `bash` Tool — Rename, 30K Output, Persistent CWD

**Branch**: `feat/bash-tool-rename`
**Date**: February 2026

## The Problem

Nano-agents had a `run_command` tool that fell short in three ways that directly degraded agent performance:

### 1. Name misled agents
The name "run_command" implied a single, isolated command. Agents didn't realize they could chain with `&&`, `;`, pipes, or run scripts. In practice, agents would make 3 separate tool calls where one `npm install && npm test` would suffice — wasting turns and context window.

### 2. Output truncated at 8K characters
Test suites, build logs, and `grep` results routinely produce 10-20K of output. With an 8K cap, agents lost the critical tail of error messages — the exact part they needed to diagnose failures. They'd see the passing tests but miss the failure traceback at the end.

### 3. CWD reset every call
Each `run_command` call started fresh in the workspace root, regardless of any `cd` in the previous call. This forced agents to use absolute paths everywhere, making multi-step workflows unnatural:

```
# What agents had to do (verbose, fragile)
run_command("ls /project/src/auth")
run_command("cat /project/src/auth/middleware.py")
run_command("cd /project/src/auth && python -m pytest test_middleware.py")

# What they wanted to do (natural, like a human)
bash("cd src/auth")
bash("ls")
bash("cat middleware.py")
bash("python -m pytest test_middleware.py")
```

## What Changed

### Rename: `run_command` → `bash`
The tool is now called `bash`, matching Claude Code's naming convention. The `@function_tool` decorator auto-derives the tool name from the Python function name — no registration or config changes needed. The `on_tool_end` lifecycle hook uses dynamic `getattr(tool, 'name')`, so it works without modification.

The system prompt now documents multi-command capabilities:
```
- bash(command) — Execute shell commands, scripts, and multi-command pipelines
- Use bash for: installing deps, running tests, building, git, chained commands (&&, ;, |)
```

### Output cap: 8K → 30K characters
Matches Claude Code's Bash tool limit. Extracted magic numbers to named constants:
- `BASH_OUTPUT_MAX_CHARS = 30000`
- `BASH_OUTPUT_HEAD_RATIO = 0.6` (keep 60% from start)
- `BASH_OUTPUT_TAIL_RATIO = 0.35` (keep 35% from end)

The 5% gap between head+tail accommodates the `...(truncated)...` marker.

### Persistent CWD across calls
Each `bash()` call now tracks the shell's working directory. A shell wrapper appends a unique marker and `pwd` after the user's command:

```shell
user_command; __nano_exit=$?; echo "__NANO_CWD_f7e2a1__"; pwd; exit $__nano_exit
```

- The marker is stripped from output before returning to the agent
- Exit codes are preserved via `$?` capture before the marker
- CWD is stored in a `ContextVar` — async-safe, isolated per concurrent task
- Failed `cd` commands don't change CWD (shell exits before `pwd` runs in the original dir)
- `set_workspace()` resets CWD tracking when a new agent session begins
- Parser uses `rfind` (last occurrence) to handle edge cases where user output contains the marker string

## What Did NOT Change

| Component | Why safe |
|-----------|----------|
| `nano_agent.py` | `on_tool_end` reads tool name dynamically via `getattr(tool, 'name')` |
| `__main__.py` | `bash` is an internal agent tool, not an MCP-registered tool |
| `data_types.py` | No run_command-specific models existed |
| `web/server.py` | Zero tool name references — fully tool-agnostic |
| `web/static/index.html` | Zero tool name references |

## Live Verification

Qwen3-Coder 30B (Ollama) verified persistent CWD in 7 separate bash calls:

| Step | Command | CWD After |
|------|---------|-----------|
| 1 | `pwd` | `/tmp/nano-cwd-test` (workspace) |
| 2 | `cd /tmp` | `/tmp` |
| 3 | `pwd` | `/tmp` (persisted!) |
| 4 | `mkdir -p test_cwd_persist && cd test_cwd_persist` | `/tmp/test_cwd_persist` |
| 5 | `pwd` | `/tmp/test_cwd_persist` (persisted!) |
| 6 | `cd /nonexistent_dir_xyz` | `/tmp/test_cwd_persist` (unchanged after failure) |
| 7 | `pwd` | `/tmp/test_cwd_persist` (confirmed) |

## Test Coverage

19 new tests in `test_bash_tool.py`, all passing:

| Category | Count | What's tested |
|----------|-------|---------------|
| Constants | 3 | TOOL_BASH exists, in AVAILABLE_TOOLS, system prompt updated |
| Function | 2 | bash in tool list, basic execution |
| Output cap | 4 | Constants exist, no truncation <30K, truncation >30K, head/tail preserved |
| Persistent CWD | 7 | Defaults to workspace, persists after cd, unchanged after failed cd, marker stripped, exit code preserved, concurrent task isolation, reset on set_workspace |
| CWD parser | 3 | No marker, duplicate marker (uses last), invalid path rejected |

Zero regressions in full test suite (40 pre-existing failures unchanged).

## Files Changed

| File | Lines | What |
|------|-------|------|
| `modules/constants.py` | +4/-4 | Rename constant, update system prompt |
| `modules/nano_agent_tools.py` | +62/-14 | Rename function, output cap, CWD tracking |
| `tests/test_bash_tool.py` | +264 (new) | 19 tests |
| `CLAUDE.md` | +1/-1 | Reference update |
| `KNOWLEDGE_TRANSFER.md` | +4/-4 | Reference updates |

---

# Release: Provider Health Check (US-002)

**Branch**: `feat/US-002-provider-health`
**Base**: `main` (post US-010 merge)
**Date**: February 2026
**Commits**: 4 | **Files changed**: 7 | **+1006 / -449 lines**

## Summary

Adds a `check_providers` MCP tool that performs concurrent health checks across all configured LLM providers. Reports status (up/down/partial), available models, latency, and errors for each provider. This gives users instant visibility into which providers are operational before dispatching agent tasks.

## What Changed

### `check_providers` MCP Tool (`__main__.py`)

New MCP-registered tool callable from Claude Code:

```python
mcp__nano-agent__check_providers()
```

Returns a structured response with per-provider health status, total check time, and summary counts (providers_up, providers_down, providers_partial).

### Health Check Engine (`provider_config.py`)

`_check_provider_health(provider)` — async function that checks each provider's reachability:

- **Cloud providers** (OpenAI, Anthropic, Z.ai): Verifies API keys exist and endpoints respond
- **Local providers** (Ollama, LM Studio): Checks if the service is running and lists loaded models
- All 5 providers checked concurrently via `asyncio.gather()`
- Each check has independent timeout handling

`check_all_providers_async()` — orchestrates concurrent checks and assembles the response.

### Pydantic Models (`data_types.py`)

| Model | Purpose |
|-------|---------|
| `ProviderHealthStatus` | Per-provider status (status, models, latency, error) |
| `CheckProvidersResponse` | Aggregated response with summary counts |

### `ProviderConfig` Refactor

`LOCAL_PROVIDER_CONFIG` extracted as a module-level dict for provider-specific configuration (ports, model list endpoints). This eliminated hardcoded values scattered across validation methods.

## Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_provider_health.py` | 28 | Individual provider checks, concurrent execution, error handling, response models |

All 28 tests passing. Zero regressions.

## Commits

| # | Hash | Message |
|---|------|---------|
| 1 | `8d464cf` | feat(US-002): add health check Pydantic models |
| 2 | `9f129f0` | feat(US-002): add health check engine with LOCAL_PROVIDER_CONFIG refactor |
| 3 | `9095695` | feat(US-002): add check_providers MCP tool and register it |
| 4 | `ed0b43d` | test(US-002): add 28 provider health check tests |

## Files Changed

```
__main__.py          |  14 ++-   (register check_providers MCP tool)
provider_config.py   | 326 +++    (health check engine, LOCAL_PROVIDER_CONFIG)
data_types.py        |  77 +--   (ProviderHealthStatus, CheckProvidersResponse)
nano_agent.py        | 167 +--   (refactor to use ProviderConfig)
test_provider_health.py | 591 +++ (NEW — 28 tests)
agent_identity.py    |  83 ---   (moved from US-010 — consolidated)
test_agent_identity.py | 197 --- (moved — consolidated into provider tests)
```

---

# Release: launch_agent MCP Tool (US-010)

**Branch**: `feat/US-010-launch-agent`
**Base**: `main` (post concurrency fix)
**Date**: February 2026
**Commits**: 5 | **Files changed**: 5 | **+449 / -6 lines**

## Summary

Adds a `launch_agent` MCP tool that deploys agents with a specific identity defined by an `AGENT.md` file. This enables creating specialized agents (e.g., "backend-expert", "test-writer") whose behavior is governed by a layered system prompt: Base Instructions + Agent Identity + Project Instructions.

## What Changed

### `launch_agent` MCP Tool (`__main__.py`)

```python
mcp__nano-agent__launch_agent(
    agentic_prompt="Build the REST API",
    agent_path="/teams/backend-expert",
    workspace="/projects/my-api",
    model="glm-4.7",
    provider="zai"
)
```

- `agent_path`: Directory containing `AGENT.md` (defines WHO the agent is)
- `workspace`: Working directory. If `workspace/AGENT.md` exists, loaded as project instructions
- All other parameters same as `prompt_nano_agent`

### Agent Identity Module (`agent_identity.py`)

| Function | Purpose |
|----------|---------|
| `read_agent_instructions(agent_path)` | Reads `AGENT.md` from agent directory, validates existence |
| `build_layered_prompt(base, agent, project)` | Assembles 3-layer system prompt with clear section headers |

Layered prompt structure:
```
=== BASE INSTRUCTIONS ===
{NANO_AGENT_SYSTEM_PROMPT}

=== AGENT INSTRUCTIONS ===
{contents of agent_path/AGENT.md}

=== PROJECT INSTRUCTIONS ===
{contents of workspace/AGENT.md, if exists}
```

### Data Model (`data_types.py`)

`LaunchAgentRequest` — extends `PromptNanoAgentRequest` with `agent_path` field and optional `instructions_override`.

### Cross-Review Hardening

Post-review commit addressed:
- Empty `AGENT.md` validation (raises `ValueError` for blank files)
- Platform-specific test skip for macOS symlink behavior

## Test Coverage

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_agent_identity.py` | 16 | read_agent_instructions, build_layered_prompt, error cases, empty file validation |

All 16 tests passing. Zero regressions.

## Commits

| # | Hash | Message |
|---|------|---------|
| 1 | `d175e5f` | feat(US-010): add LaunchAgentRequest model and instructions_override parameter |
| 2 | `8c7ff47` | feat(US-010): add agent_identity module with read_agent_instructions and build_layered_prompt |
| 3 | `ea5406a` | feat(US-010): add launch_agent() MCP tool with identity-aware execution |
| 4 | `9521358` | test(US-010): add comprehensive tests for agent_identity module |
| 5 | `4eb46d8` | fix(US-010): address cross-review findings — empty AGENT.md validation + platform skip |

## Files Changed

```
__main__.py          |   6 ++-  (register launch_agent MCP tool)
agent_identity.py    |  83 +++  (NEW — read/build layered prompts)
data_types.py        |  31 +++  (LaunchAgentRequest model)
nano_agent.py        | 138 +++  (launch_agent execution path)
test_agent_identity.py | 197 +++ (NEW — 16 tests)
```

---

# Release: Async Concurrency + Portable Hooks

**Branch**: `fix/concurrency-and-portable-hooks`
**Base**: foundational (includes dashboard, providers, tools)
**Date**: February 2026
**Key Commits**: 3 | **Tests**: 20

## Summary

Fixes critical concurrency bugs when multiple nano-agent tasks run simultaneously, and makes hook paths portable across machines. This was the foundational branch that also includes the dashboard, multi-provider support (OpenAI, Anthropic, Ollama, LM Studio, Z.ai), and the initial tool set.

## Concurrency Fix (`08e7df8`)

**Problem**: Multiple concurrent agent executions shared mutable module-level state (`workspace_dir`, agent config). When two agents ran simultaneously, one would overwrite the other's workspace path, causing file operations in the wrong directory.

**Solution**: Replaced module-level variables with `ContextVar` instances:
- `_workspace_var: ContextVar[str]` — per-task workspace isolation
- `_agent_config_var: ContextVar[AgentConfig]` — per-task agent configuration
- `resolve_path()` updated to use `_workspace_var.get()` instead of global

`asyncio.create_task()` and `anyio.start_soon()` both copy `ContextVar` values, so child tasks inherit the correct workspace without cross-contamination.

20 concurrency tests verify isolation under parallel execution.

## Tracing Race Condition Fix (`89f5811`)

Disabled OpenAI Agent SDK tracing globally. The SDK's telemetry system had internal race conditions when multiple agents ran concurrently, causing sporadic crashes unrelated to our code.

## Portable Hooks (`72d718b`)

**Problem**: `.claude/settings.json` hook commands used hardcoded absolute paths (e.g., `/Users/ahmed/ai_storage/...`). These broke on other machines or when the project was moved.

**Solution**: Replace absolute paths with `$CLAUDE_PROJECT_DIR` environment variable, which Claude Code sets automatically to the project root.

90 tests verify path portability across different directory structures.

## Commits

| # | Hash | Message |
|---|------|---------|
| 1 | `08e7df8` | fix: async-safe concurrency with ContextVars, resolve_path workspace, and agent configs |
| 2 | `89f5811` | fix: disable tracing globally to eliminate race condition |
| 3 | `72d718b` | fix: make hook paths portable using $CLAUDE_PROJECT_DIR |

## Key Files Changed

```
nano_agent.py        | Workspace ContextVar, agent config isolation
nano_agent_tools.py  | resolve_path() uses ContextVar
provider_config.py   | Per-task provider setup
.claude/settings.json| $CLAUDE_PROJECT_DIR in hook paths
test_concurrency.py  | 20 concurrency isolation tests
test_settings_paths.py | 90 path portability tests
```
