# Release Notes: GLM-5 Model Support

**Branch**: `feat/glm5-model`
**Base**: `main` (post tool-resilience merge)
**Date**: 2026-02-13
**Commits**: 2 | **Files changed**: 2 | **+61 / -1 lines**

---

## Summary

Adds GLM-5 (744B MoE, 44B active) as a Z.ai provider model alongside existing GLM-4.7 and GLM-4.5-air. GLM-5 is Z.ai's frontier reasoning model with native chain-of-thought thinking support enabled by default.

No architecture changes — GLM-5 uses the same `LitellmModel` bridge and Coding Plan endpoint (`/api/anthropic`) as GLM-4.7.

---

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

---

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

---

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

---

## Commits

| # | Hash | Message |
|---|------|---------|
| 1 | `75e41cb` | feat(zai): add GLM-5 model support alongside GLM-4.7 |
| 2 | `95d8623` | feat(zai): enable GLM-5 thinking (chain-of-thought reasoning) |

---

## Files Changed

```
constants.py              | 12 +++++++++++-  (1 modified, 11 added)
test_model_capabilities.py | 50 ++++++++++++++++++++++  (50 added)
```

---

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
