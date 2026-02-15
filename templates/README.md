# Templates Have Moved

Templates are now bundled inside the Python package for runtime discoverability.

**New location**: `apps/nano_agent_mcp_server/src/nano_agent/templates/`

This follows PyPA best practice: data files needed at runtime must live inside the package boundary, accessible via `importlib.resources`.

## After Installation

Templates are available as MCP resources. In a Claude Code session:

```
ListMcpResourcesTool(server="nano-agent")
ReadMcpResourceTool(server="nano-agent", uri="nano-agent://templates/agents/nano-reviewer.md")
```

## For Development

Browse the templates directly:

```bash
ls apps/nano_agent_mcp_server/src/nano_agent/templates/
```
