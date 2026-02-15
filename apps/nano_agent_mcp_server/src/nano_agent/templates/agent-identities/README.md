# AGENT.md Identity Templates

This directory contains agent identity templates that define specialized roles and behavioral guidelines for AI coding agents.

## What Are AGENT.md Files?

AGENT.md files are plain Markdown documents that define an agent's role, persona, and behavioral guidelines. When you launch an agent using the `launch_agent` MCP tool, it reads the AGENT.md file from the specified agent path and builds a three-layer system prompt:

1. **Base Layer**: The NANO_AGENT_SYSTEM_PROMPT (includes all 13 tools and core behavioral rules)
2. **Agent Layer**: The AGENT.md content (role-specific persona and guidelines)
3. **Project Layer**: Project-specific context if provided

This architecture allows agents to share core tool knowledge while having distinct personalities and approaches.

## How They Differ from Claude Code Templates

AGENT.md files are simpler than Claude Code agent templates:
- **No YAML frontmatter** — Just plain Markdown
- **No tool listings** — The base system prompt already lists all 13 tools
- **Role-focused** — Only define persona, approach, and behavioral guidelines
- **Portable** — Can be stored anywhere and referenced via `agent_path`

## Installation

1. Copy this entire directory to your desired location
2. When launching an agent, set `agent_path` to point to a specific identity directory:
   - `agent_path: "/path/to/general-coder"` for general coding tasks
   - `agent_path: "/path/to/code-reviewer"` for code review sessions
   - `agent_path: "/path/to/tdd-engineer"` for test-driven development
   - `agent_path: "/path/to/backend-expert"` for backend development

## Available Templates

### general-coder
Versatile coding agent that adapts to any project. Focuses on reading existing code first, matching project style, writing tests, and handling errors gracefully. Ideal for day-to-day development tasks.

### code-reviewer
Code review specialist that systematically examines changes via git_diff, checks for logic errors, security issues, error handling, naming conventions, test coverage, and API contracts. Reports findings by severity with specific file:line references.

### tdd-engineer
Test-driven development practitioner that follows strict RED-GREEN-REFACTOR discipline. Never writes code without a failing test first, runs tests after every change, keeps tests focused, and writes minimal code to pass.

### backend-expert
Backend development specialist focusing on API design, database modeling, input validation, connection pooling, and error handling. Emphasizes security (parameterized queries, sanitization, auth/authz) and performance (pooling, pagination, caching).

## What NOT to Include in AGENT.md

- **Tool listings**: The base prompt already provides all 13 tools with descriptions
- **System prompt content**: Core behavioral rules are defined in NANO_AGENT_SYSTEM_PROMPT
- **Tool usage instructions**: How to use tools is already covered
- **Duplicate constraints**: Don't repeat what's in the base prompt

AGENT.md files should only add role-specific personality, workflow preferences, and domain expertise on top of the foundation already provided.
