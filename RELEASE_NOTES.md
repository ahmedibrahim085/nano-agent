# Release: Qwen Cloud Provider + ModelCapability Pipeline Extension

**Branch:** `feat/qwen-provider`
**Date:** February 2026
**Commits:** 16 (9 feat, 4 fix, 3 docs)
**Scope:** 16 files changed, +1549 / -32 lines
**New Tests:** 60 (29 auth + 11 provider + 20 model capabilities)

---

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

---

## Dashboard Changes

The web dashboard (`nano-web`, port 8484) is updated for 6 providers:

- **Grid:** Responsive layout updated to `lg:grid-cols-6`
- **Qwen card:** Orange color theme (`bg-orange-500/20 text-orange-400 border-orange-500/30`)
- **Status:** Shows "online" when `~/.qwen/oauth_creds.json` exists, "no_api_key" otherwise
- **Config:** Qwen shows "Not Required" in the Configuration section (OAuth-based, no env var needed)
- **Health check:** Qwen included in the concurrent 6-provider health check

---

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

---

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

---

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

---

## Known Limitations

1. **No concurrent token refresh locking.** `get_valid_token()` has no mutex. If two agents call it simultaneously with an expired token, both will attempt to refresh — the second may fail with `invalid_grant`. This is acceptable for current single-agent usage patterns and is a design decision deferred to a future concurrent-agents feature.

2. **Token baked at agent creation time.** The OAuth token is fetched once during `create_agent()` and stored as a fixed `api_key` in the `AsyncOpenAI` client. Qwen tokens expire (default 6 hours). Long-running sessions may encounter mid-execution 401 errors. A proper fix requires a custom `httpx.Auth` class, which is beyond the scope of this release.

3. **curl dependency.** Token refresh requires `curl` on the system. Checked at refresh time with `shutil.which("curl")` — raises `QwenAuthError("curl not found — required for Qwen token refresh")` if missing.

---

## Breaking Changes

**None.** All changes are additive:
- New `ModelCapability` fields default to `None` — existing models unaffected
- `"qwen"` added to `Literal` provider types — additive, no removals
- Dashboard grid expanded — responsive, no layout changes for existing providers
- All 132 scoped tests pass with zero regressions

---

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

---

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
---

# Release: `bash` Tool — Rename, 30K Output, Persistent CWD

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
