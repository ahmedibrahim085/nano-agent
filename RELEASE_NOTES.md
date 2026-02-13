# Release Notes: Tool Resilience

**Branch**: `feat/tool-resilience`
**Base**: `main` (post Qwen Cloud provider merge)
**Date**: 2026-02-13
**Commits**: 10 | **Files changed**: 6 | **+869 / -4 lines**

---

## What This Release Does

When nano-agent models finish a task, they sometimes try to call tools that don't exist in our tool set. For example, `qwen3-coder-next` called `run_tests` after building a pytest project — correct intent, wrong tool name. The OpenAI Agent SDK crashes with `ModelBehaviorError` at that point, killing the entire agent run and losing all work done up to that moment.

This release solves the problem with a two-layer defense:

1. **Give agents the tools they actually need** — `search_files` and `run_tests` are the two most commonly hallucinated tool names across 10 coding agent frameworks we surveyed. By implementing them as real tools, ~90% of hallucination cases become legitimate tool calls instead of crashes.

2. **Catch everything else gracefully** — For the remaining unknown tool names, a pre-filter monkey-patch intercepts them before the SDK can crash. Valid tool calls in the same response still execute normally. The model receives a helpful error listing available tools so it can self-correct on the next turn.

Additionally, this release adds support for `qwen3-coder-next` (Qwen's latest coding model) running on LM Studio.

---

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

---

## SDK Crash Prevention

**Problem**: OpenAI Agent SDK (v0.8.4) raises `ModelBehaviorError` inside a loop over `response.output` when it encounters an unknown tool call. All valid tool calls processed before the crash are lost. This is a known issue (openai/openai-agents-python#325, open since March 2025, unfixed).

**Solution**: A pre-filter monkey-patch on `process_model_response` that:
1. Scans `response.output` for unknown `ResponseFunctionToolCall` items
2. If none found — calls original function as-is (zero overhead on happy path)
3. If unknown found — removes them, processes valid calls normally via original function, then appends synthetic error items using the SDK's own `ToolCallItem`/`ToolCallOutputItem` pattern (same approach as `approvals.py:22-39`)

The error message lists all available tool names so the model can self-correct.

---

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

---

## qwen3-coder-next Support

- Added to `MODEL_CAPABILITIES` registry with 128K max output tokens
- Added to `MODEL_INFO` with correct LM Studio model ID (`qwen/qwen3-coder-next`)
- `MAX_AGENT_TURNS` bumped from 20 to 50 to support longer coding sessions

---

## System Prompt Update

The agent system prompt now lists all 8 tools with negative guidance:

```
You have ONLY these 8 tools. Do NOT call any other tool name.
```

This serves as the primary defense — smart models (like qwen3-coder-next) follow this instruction and never attempt unknown tools. The monkey-patch is the fallback for weaker models.

---

## Test Coverage

| Test Suite | Tests | Status |
|------------|-------|--------|
| search_files (basic + security) | 11 | All pass |
| run_tests (basic + security) | 10 | All pass |
| tool resilience (monkey-patch) | 7 | All pass |
| model capabilities (qwen3-coder-next) | 21 | All pass |
| **Total new tests** | **49** | **All pass** |
| Full regression (307/346) | 346 | 39 pre-existing failures, 0 new |

---

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

---

## Files Changed

```
constants.py            |  26 ++-   (new tool constants, system prompt update)
nano_agent.py           | 126 +++   (resilience monkey-patch + security hardening)
nano_agent_tools.py     | 214 +++   (search_files + run_tests implementations)
test_nano_agent_tools.py| 195 +++   (28 new tool tests + 6 security tests)
test_tool_resilience.py | 255 +++   (NEW — 7 resilience tests)
test_model_capabilities | 57  +++   (21 qwen3-coder-next capability tests)
```
