# Nano-Agent Knowledge Transfer

> Comprehensive record of 3 development sessions (Feb 7-8, 2026).
> This document ensures continuity when starting new sessions from this project directory.

---

## 1. What Is Nano-Agent?

An MCP server that lets Claude Code delegate tasks to **subagents** running on different LLM providers. Built on the **OpenAI Agent SDK** (`openai-agents`) with provider bridging for universal compatibility.

**One-line**: Claude Code sends a task via MCP → nano-agent creates an autonomous agent on any provider → agent uses tools (read/write/edit files, run commands) → returns result to Claude.

---

## 2. Supported Providers (5)

| Provider | Protocol | Models | Auth | Base URL |
|----------|----------|--------|------|----------|
| `openai` | OpenAI native | gpt-5, gpt-5-mini, gpt-5-nano, gpt-4o | `OPENAI_API_KEY` | Default |
| `anthropic` | OpenAI-compat | claude-opus-4-1, opus-4, sonnet-4, haiku-3 | `ANTHROPIC_API_KEY` | `api.anthropic.com/v1/` |
| `ollama` | OpenAI-compat | Dynamic (queries API) | None | `127.0.0.1:11434/v1` |
| `lmstudio` | OpenAI-compat | Dynamic (queries API) | None | `127.0.0.1:1234/v1` |
| `zai` | **Anthropic** (via LiteLLM) | glm-4.7, glm-4.5-air | `Z_AI_API_KEY` | `api.z.ai/api/anthropic` |

### Z.ai Architecture (Key Decision)

Z.ai only speaks Anthropic Messages API protocol. The OpenAI Agent SDK expects OpenAI-format responses. Solution:

```
Agent SDK → LitellmModel(model="anthropic/glm-4.7", base_url="https://api.z.ai/api/anthropic")
         → LiteLLM translates OpenAI format → Anthropic format → sends to Z.ai
         → Z.ai responds in Anthropic format → LiteLLM translates back → Agent SDK
```

**Why not native Anthropic SDK?** The Agent SDK's `Agent` class requires OpenAI-compatible model objects. LitellmModel is the official bridge.

---

## 3. Agent Tools (6)

All tools use `@function_tool` decorator (universal compatibility across all providers — unlike `ShellTool`/`ApplyPatchTool` which are OpenAI-only).

| Tool | Function | Key Detail |
|------|----------|------------|
| `read_file` | Read file contents | Returns content as string |
| `write_file` | Create/overwrite files | Creates parent dirs automatically |
| `edit_file` | Surgical text replacement | Requires exact `old_str` match |
| `list_directory` | List directory contents | Returns formatted listing |
| `get_file_info` | File metadata | Size, modified date, permissions |
| `bash` | Execute shell commands/pipelines | `asyncio.create_subprocess_shell`, 120s timeout, 30K-char output cap, persistent CWD |

### Why `@function_tool` Over `ShellTool`?

`ShellTool` and `ApplyPatchTool` use OpenAI's proprietary `LocalShellCall`/`LocalShellOutput` protocol. They only work with OpenAI models. `@function_tool` uses standard function calling — works universally across all 6 providers. This was a critical architectural decision.

### Workspace Isolation

Shell commands run with `cwd=workspace_dir`. Module-level `_workspace_dir` variable, set per-invocation via `set_workspace()`. Inspired by OpenAI Cookbook's `ShellExecutor` pattern.

---

## 4. Web Dashboard

**Entry point**: `nano-web` command → FastAPI server on port 8484.
**Frontend**: Single-file HTML (`web/static/index.html`, 906 lines), Tailwind CSS CDN, vanilla JS, dark theme (slate-900/800).

### 6 Sections

1. **Providers** — Shows 6 providers with status indicators
2. **Models** — Lists available models per provider (dynamic for Ollama/LM Studio)
3. **Playground** — Execute prompts with any provider/model, streaming-style output
4. **History** — In-memory execution log (max 100), shows timing, tokens, metadata
5. **Configuration** — View/edit runtime config (model defaults, temperature, etc.)
6. **Agent Configs** — CRUD for `~/.claude/agents/nano-agent-*.md` files with modal editor

### API Routes (10)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Serve dashboard HTML |
| GET | `/api/providers` | List providers with status |
| GET | `/api/models` | List models (dynamic for local providers) |
| POST | `/api/run` | Execute agent prompt |
| GET | `/api/history` | Get execution history |
| DELETE | `/api/history` | Clear history |
| GET | `/api/config` | Get current config |
| PUT | `/api/config` | Update config |
| GET | `/api/agents` | List agent configs |
| GET/PUT/DELETE | `/api/agents/{name}` | CRUD agent config |

---

## 5. Key Files Guide

```
apps/nano_agent_mcp_server/
├── src/nano_agent/
│   ├── __main__.py          # MCP server entry (FastMCP), registers prompt_nano_agent tool
│   ├── cli.py               # CLI entry points (nano-cli, nano-web)
│   ├── modules/
│   │   ├── constants.py     # All config: models, prompts, tool names, error messages
│   │   ├── data_types.py    # Pydantic models (request/response/config/tracking)
│   │   ├── files.py         # Path resolution utilities (resolve_path, is_path_safe)
│   │   ├── nano_agent.py    # Core: prompt_nano_agent(), _execute_nano_agent_async(), RichLoggingHooks
│   │   ├── nano_agent_tools.py  # 6 @function_tool definitions + workspace management
│   │   └── provider_config.py   # ProviderConfig.create_agent() — 6-provider factory
│   └── web/
│       ├── __init__.py
│       ├── server.py        # FastAPI dashboard backend (10 routes)
│       └── static/
│           └── index.html   # Dashboard frontend (906 lines)
├── pyproject.toml           # Package config, entry points, dependencies
└── uv.lock                  # Locked dependencies
```

---

## 6. Bugs Fixed (With Root Causes)

### Bug 1: Ollama Dual-Instance IPv4/IPv6 Split
- **Symptom**: `curl localhost:11434/api/tags` returns empty model list
- **Root cause**: Two Ollama instances — Ollama.app (IPv6 `::1:11434`) and brew (IPv4 `0.0.0.0:11434`). `localhost` resolves to IPv6 first, hitting the wrong instance.
- **Fix**: Use `127.0.0.1` (IPv4 explicit) instead of `localhost`
- **Diagnosis**: `lsof -i :11434` shows both PIDs

### Bug 2: OpenAI Telemetry Leak
- **Symptom**: Non-OpenAI providers send telemetry to OpenAI
- **Root cause**: `setup_provider()` only disabled tracing when `OPENAI_API_KEY` was missing
- **Fix**: Unconditionally `set_tracing_disabled(True)` for all non-OpenAI providers

### Bug 3: Static Model Whitelist
- **Symptom**: New Ollama/LM Studio models can't be used without code changes
- **Fix**: Dynamic validation queries the running service API at runtime

### Bug 4: CLI check_api_key Always Demanded OpenAI Key
- **Symptom**: `nano-cli` fails for Ollama even though no API key needed
- **Fix**: Made `check_api_key()` provider-aware using `PROVIDER_REQUIREMENTS` lookup

### Bug 5: Pydantic Serialization Warnings (Not Fixed — Cosmetic)
- **Symptom**: `PydanticSerializationUnexpectedValue` for `ServerToolUse` with Z.ai via LitellmModel
- **Impact**: Warning noise only, non-blocking
- **Status**: Pre-existing in litellm integration, low priority

---

## 7. Architecture Decisions & Rationale

| Decision | Why | Alternative Considered |
|----------|-----|----------------------|
| `@function_tool` for all tools | Universal compatibility across 6 providers | `ShellTool`/`ApplyPatchTool` — OpenAI-only |
| `LitellmModel` for Z.ai | Bridges Anthropic protocol to OpenAI Agent SDK | Native Anthropic SDK — incompatible with Agent SDK |
| Module-level `_workspace_dir` | Simple, per-invocation isolation | Class-based workspace — over-engineered for single-tool context |
| In-memory execution history | Simple, no persistence needed for dev tool | SQLite/file-based — YAGNI |
| Single-file HTML dashboard | Quick iteration, no build step | React/Vue SPA — over-engineered |
| `127.0.0.1` over `localhost` | Avoids IPv6/IPv4 ambiguity on macOS | DNS resolution fix — fragile |

---

## 8. Performance Benchmarks (Feb 7, 2026)

| Provider | Model | Task | Time | Cost |
|----------|-------|------|------|------|
| ollama | gpt-oss:20b | List files | 9.9s | $0.00 |
| ollama | qwen3-coder:30b | Code analysis | 20.2s | $0.00 |
| openai | gpt-5-mini | Simple task | ~2s | $0.0012 |
| zai | glm-4.7 | Q&A | 3.0s | $0.00* |
| zai | glm-4.7 | Write + execute hello.py | 5.99s | $0.00* |
| zai | glm-4.5-air | List files (tool use) | 6.4s | $0.00* |

---

## 9. Environment Variables

| Variable | Purpose | Where Set |
|----------|---------|-----------|
| `OPENAI_API_KEY` | OpenAI provider auth | `.env` |
| `ANTHROPIC_API_KEY` | Anthropic provider auth | `.env` |
| `Z_AI_API_KEY` | Z.ai provider auth | `.env` |
| `ENGINEER_NAME` | Display name in CLI | `.env` |

---

## 10. Agent Configs (6 Global)

Located at `~/.claude/agents/nano-agent-*.md`. These define Claude Code subagent types.

| Agent | Model | Provider | Use Case |
|-------|-------|----------|----------|
| `nano-agent-gpt-oss-20b` | gpt-oss:20b | ollama | Quick file ops, simple tasks (free, local) |
| `nano-agent-gpt-oss-120b` | gpt-oss:120b | ollama | Complex tasks, best local model (free, 65GB) |
| `nano-agent-qwen3-coder` | qwen3-coder:30b | ollama | Coding tasks (free, local, 18GB) |
| `nano-agent-gemma3` | gemma3:27b | ollama | General tasks (free, local, 17GB) |
| `nano-agent-magistral` | magistral:latest | ollama | Reasoning tasks (free, local, 14GB) |
| `nano-agent-zai-glm47` | glm-4.7 | zai | Powerful cloud reasoning (Z.ai API) |

There are also **repo-level** agent configs at `.claude/agents/` (different set — OpenAI/Anthropic models). These came from upstream and are part of the hook system.

---

## 11. Testing Commands

```bash
# Start web dashboard
nano-web

# Quick test any provider via curl
curl -s -X POST http://localhost:8484/api/run \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is 2+2?","provider":"zai","model":"glm-4.7"}'

# Verify Ollama models
curl -s http://127.0.0.1:11434/api/tags | python3 -m json.tool

# Verify LM Studio models
curl -s http://127.0.0.1:1234/v1/models | python3 -m json.tool

# Reinstall after code changes
cd apps/nano_agent_mcp_server && uv tool install -e . --force
```

---

## 12. What's Working (Verified)

- [x] All 6 providers create agents correctly
- [x] Z.ai GLM-4.7 can use tools (write_file, bash verified)
- [x] Web dashboard all 6 features functional (E2E tested with screenshots)
- [x] `bash` with workspace isolation works (persistent CWD across calls)
- [x] Agent autonomously wrote hello.py and executed it via bash
- [x] Dynamic model discovery for Ollama/LM Studio
- [x] Execution history tracking in dashboard

## 13. What's NOT Tested Yet

- [ ] Complex multi-file coding task with Nano doing the heavy lifting
- [ ] Workspace field exposed in dashboard Playground UI
- [ ] Anthropic provider (API key empty in .env)
- [ ] LM Studio provider (needs LM Studio running)
- [ ] Error recovery when agent gets stuck in a loop
- [ ] Concurrent agent executions
- [ ] Token usage tracking accuracy

## 14. Next Steps (From Last Session)

1. **Make Nano do heavy lifting** — Test complex real-world coding tasks
2. **Add workspace to Playground UI** — Backend supports it, frontend doesn't expose it
3. **Improve error handling** — Agent can get stuck, needs graceful timeout/retry
4. **Persist execution history** — Currently in-memory, lost on restart
5. **Add edit_file tool to dashboard** — Currently only in agent, not in web UI

---

## 15. Git History

Forked from `github.com/disler/nano-agent`. Our work is 8 commits on top of upstream `main`:

```
4c91c8b fix: make check_api_key provider-aware
ddac3d6 feat: add LM Studio, Z.ai providers + fix Ollama IPv4 + telemetry
458e0eb feat: extend type definitions and constants for new providers
60a0688 deps: add litellm for Z.ai Anthropic-to-OpenAI protocol bridge
47d0f29 feat: add web dashboard backend with FastAPI
90a650e feat: add dashboard frontend (generated by Qwen3-Coder)
cd6d0f4 feat: add execution history, config manager, and agent editor (features 4-6)
1fa5c4c feat: add run_command tool and workspace support for autonomous coding
```

**Remotes**:
- `origin` → `github.com/ahmedibrahim085/nano-agent` (our fork)
- `upstream` → `github.com/disler/nano-agent` (original)

---

## 16. Session History Reference

Previous sessions stored at `~/.claude/projects/-Users-<username>/`:
- `08ec79f0` — Session 1: Initial setup, multi-provider, bug fixes
- `83dc4b3b` — Session 2+3: Dashboard, run_command, E2E testing, migration
- `9d5bc3f6` — Related session

Copies kept in project-scoped memory for reference.
