# Nano-Agent Project Instructions

## Overview
MCP server that delegates tasks from Claude Code to subagents on 6 LLM providers (OpenAI, Anthropic, Ollama, LM Studio, Z.ai, Qwen). Built on OpenAI Agent SDK.

## Quick Reference
- **Package**: `apps/nano_agent_mcp_server/`
- **Reinstall after changes**: `cd apps/nano_agent_mcp_server && uv tool install -e . --force`
- **Start dashboard**: `nano-web` (port 8484)
- **Knowledge base**: See `KNOWLEDGE_TRANSFER.md` for full context

## Key Architecture Rules
- All agent tools MUST use `@function_tool` (not `ShellTool`/`ApplyPatchTool`) for cross-provider compatibility
- Z.ai uses `LitellmModel` bridge — do not attempt native Anthropic SDK integration
- Ollama: always use `127.0.0.1` not `localhost` (IPv4/IPv6 dual-instance bug)
- Workspace isolation: `bash` uses `cwd=workspace_dir` (persistent across calls), set via `set_workspace()`

## File Layout
```
apps/nano_agent_mcp_server/src/nano_agent/
├── __main__.py              # MCP entry point
├── cli.py                   # CLI commands
├── modules/
│   ├── constants.py         # Config, prompts, model lists
│   ├── data_types.py        # Pydantic models
│   ├── nano_agent.py        # Core agent execution
│   ├── nano_agent_tools.py  # 6 @function_tool definitions
│   └── provider_config.py   # 6-provider factory
└── web/
    ├── server.py            # FastAPI backend
    └── static/index.html    # Dashboard frontend
```

## Remotes
- `origin` → `github.com/ahmedibrahim085/nano-agent` (our fork)
- `upstream` → `github.com/disler/nano-agent` (original)
