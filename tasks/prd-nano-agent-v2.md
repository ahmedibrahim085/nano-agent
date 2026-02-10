# PRD: Nano-Agent MCP Server v2.0 Roadmap

## Introduction

Nano-agent is an MCP server that bridges Model Context Protocol with OpenAI's Agent SDK, enabling autonomous agent execution across multiple LLM providers from a single interface. Users describe work in natural language, and nano-agent delegates it to the optimal LLM provider — OpenAI, Anthropic, Ollama, LM Studio, or Z.ai.

**v1.0 (shipped)** established the core: single-agent execution, 6 file system tools, workspace isolation, token tracking, and a web dashboard. The recent concurrency fix (ContextVars) unlocked **parallel multi-provider execution** — 4+ agents running simultaneously across different providers with zero crosstalk.

**v2.0** builds on this foundation with 9 features across 4 phases, transforming nano-agent from a single-call tool into an intelligent, resilient, multi-agent orchestration platform with persistent memory.

### Problem Statement

Today, nano-agent treats all LLM providers identically — same system prompt, no fallback when a provider fails, no way to chain agents, and no memory between sessions. Users must manually:
- Craft provider-specific instructions (Qwen needs different prompting than GPT-5)
- Check which providers are available before launching work
- Handle failures by re-running with a different provider
- Orchestrate multi-agent workflows step by step
- Re-explain project context every time (agent starts from scratch each session)

### Vision

An MCP server where users specify **what** they want done, and nano-agent handles **how** — picking the right model, using provider-optimized instructions, falling back on failure, chaining agents for complex workflows, and remembering what it learned about each project.

---

## Goals

- **G1**: Improve agent output quality through provider-specific instructions and project memory
- **G2**: Eliminate wasted execution cycles from provider failures (zero-downtime agent calls)
- **G3**: Reduce manual orchestration effort for multi-step workflows
- **G4**: Expose provider health as a first-class MCP tool for informed decision-making
- **G5**: Enable community contributions of instruction sets and execution templates
- **G6**: Give agents persistent context across sessions (project history + learned patterns)

---

## Shipped Baseline (v1.x)

These capabilities are already live and form the foundation for v2.0:

| Capability | Status | Details |
|---|---|---|
| Single-agent execution | Shipped | `prompt_nano_agent(agentic_prompt, model, provider, workspace)` |
| 5 LLM providers | Shipped | OpenAI, Anthropic, Ollama, LM Studio, Z.ai |
| 6 file system tools | Shipped | read_file, write_file, edit_file, list_directory, get_file_info, bash (renamed from run_command) |
| Workspace isolation | Shipped | ContextVar-based per-task workspace via `set_workspace()`, persistent CWD across bash calls |
| Parallel execution | Shipped | Multiple concurrent agents with zero crosstalk (ContextVars) |
| Token tracking | Shipped | Per-execution token counts and cost calculation |
| Web dashboard | Shipped | `nano-web` on port 8484 |
| Async provider validation | Shipped | `httpx.AsyncClient` for non-blocking health checks |

---

## Design Decisions (Aligned)

These decisions were made during PRD planning and are binding for all spec files:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Instruction file format | Markdown + optional YAML frontmatter | Industry standard (Claude Code, GitHub Copilot, AGENTS.md) |
| Instruction location | Both: built-in in package + user override in `~/.nano-agent/instructions/` | Maximum flexibility |
| Instruction layering | Concatenate with section headers | Industry best practice. Each layer gets `## Section Header`. Base first, user custom last. |
| Instruction selection | Auto + manual override | Auto-load based on provider/model; user overrides with `instructions` parameter |
| Workspace instructions | Check `{workspace}/AGENT.md` | Per-project instructions, scoped by workspace parameter. Industry standard. |
| Fallback default chain | GLM-4.7 → Qwen-Coder-Next → Qwen3-Coder | User's preferred model priority order |
| Execution templates | 6 shipped: tdd, implement-feature, code-review, refactor, debug, document | Comprehensive coverage from day one |
| Smart routing | Configurable tier mapping with defaults | Not heuristic-based. User defines tier→model mapping. Defaults: heavy=GLM-4.7, standard=Qwen-Next, light=Qwen3-Coder |
| Pipeline tool | Separate MCP tool: `prompt_pipeline()` | Clean separation from `prompt_nano_agent`. Different input schema. |
| Pipeline error handling | Halt and return partial results | Stop at failed step. Return completed step results + error. User decides next action. |
| Streaming | Important for debugging | Progress callbacks during execution for visibility into tool calls and agent state |
| Git tools | Always available (not opt-in) | Included in default tool set alongside existing 6 tools. Safety guards prevent destructive ops. |
| Agent memory | History + context, project + global storage | Agents remember what they did (history) and what they learned (context). Stored per-project and globally. |
| Health check | Separate MCP tool | New `check_providers()` tool, independent from `prompt_nano_agent` |
| Budget/cost control | Deprioritized | User primarily uses local LLMs (free). May add later as simple `max_turns` limit. |
| Sandboxed execution | Removed from roadmap | Not needed for current workflow. Local LLMs + controlled workspaces. |
| Result caching | Replaced by Agent Memory | Agent Memory subsumes caching with richer context persistence. |
| Spec granularity | Both levels | High-level tasks for humans + sub-tasks scoped for nano-agent delegation |

---

## User Stories

### Phase 1: Foundations (v2.0)

#### US-010: Agent Identity (launch_agent Tool) — SHIPPED (PR #7)
**Description:** As an AI engineer, I want to deploy agents with specific identities (AGENT.md) to work on any project, so that I can build reusable agent personas for my team.

**Status:** Shipped. Branch `feat/US-010-launch-agent`, 5 commits, +449/-6 lines, 17 tests.

**Shipped capabilities that downstream stories can build on:**
- `build_layered_prompt()` — assembles system prompt from sections with `## Headers`
- `read_agent_instructions()` — reads and validates AGENT.md files
- `instructions_override` parameter on `_execute_nano_agent_async()` — clean injection point
- Workspace AGENT.md detection with dedup logic
- `LaunchAgentRequest` Pydantic model

**Acceptance Criteria:**
- [x] New MCP tool: `launch_agent(agentic_prompt, agent_path, workspace, provider, model)`
- [x] `agent_path` is required — path to directory containing the agent's AGENT.md
- [x] Agent reads `{agent_path}/AGENT.md` and includes it as `## Agent Instructions` in system prompt
- [x] If `{workspace}/AGENT.md` also exists, includes it as `## Project Instructions`
- [x] System prompt layers: Base → Agent Instructions → Project Instructions → Workspace dir
- [x] `agent_path` validated: error if path doesn't exist or AGENT.md not found
- [x] Instruction files are plain Markdown (no YAML frontmatter required)
- [x] Reuses existing agent execution infrastructure (_execute_nano_agent_async)
- [x] Separate from prompt_nano_agent — different MCP tool, different schema
- [x] Response uses same PromptNanoAgentResponse schema
- [x] Tests for: agent loading, workspace loading, both loaded, missing AGENT.md, agent_path validation

#### US-002: Provider Health Check — SHIPPED
**Description:** As an AI engineer, I want to check which providers and models are available before launching agents so that I can make informed decisions.

**Status:** Shipped. Branch `feat/US-002-provider-health`, 3 commits, 28 tests.

**Acceptance Criteria:**
- [x] New MCP tool: `check_providers()` returning status of all configured providers
- [x] Response includes: provider name, status (up/down), available models list, response latency (ms)
- [x] Reuses existing `validate_provider_setup_async()` logic
- [x] All 5 providers checked concurrently using `httpx.AsyncClient`
- [x] API-key providers (OpenAI, Anthropic, Z.ai): check key is set + endpoint reachable
- [x] Local providers (Ollama, LM Studio): check service running + list loaded models
- [x] Registered as a second tool on the MCP server alongside `prompt_nano_agent`
- [x] Tests for all provider states (up, down, partial model availability)

---

### Phase 2: Resilience & Productivity (v2.1)

#### US-003: Provider Fallback Chain
**Description:** As an AI engineer, I want to specify a fallback chain of providers so that if one fails, the next is tried automatically.

**Acceptance Criteria:**
- [ ] New `providers` parameter accepting an ordered list: `["zai/glm-4.7", "lmstudio/qwen3-coder-next", "ollama/qwen3-coder:30b"]`
- [ ] Default fallback chain: GLM-4.7 (Z.ai) → Qwen-Coder-Next (LM Studio) → Qwen3-Coder (Ollama)
- [ ] Uses Health Check (US-002) to skip known-down providers before attempting
- [ ] Tries each provider in order until one succeeds
- [ ] Response includes `provider_attempts` array: `[{provider, status, error_or_null, latency}]`
- [ ] Original `provider` + `model` parameters still work (single provider, no fallback)
- [ ] Tests for: first succeeds, first fails + second succeeds, all fail, health-check skip

#### US-004: Execution Templates
**Description:** As an AI engineer, I want pre-built prompt templates for common workflows so that I don't write the same spec structure repeatedly.

**Acceptance Criteria:**
- [ ] New `template` parameter on `prompt_nano_agent`: `template="tdd"`
- [ ] 6 shipped templates: `tdd`, `implement-feature`, `code-review`, `refactor`, `debug`, `document`
- [ ] Template format: Markdown with YAML frontmatter (metadata: name, description, required_vars, instructions)
- [ ] Template variables use `{variable_name}` syntax, substituted at runtime from `template_vars` dict parameter
- [ ] Built-in templates in `<package>/templates/` directory
- [ ] User-defined templates in `~/.nano-agent/templates/` override built-in of same name
- [ ] Templates inject content via `instructions_override` (infrastructure from US-010)
- [ ] Tests for template loading, variable substitution, missing variables, and custom templates

---

### Phase 3: Intelligence & Orchestration (v2.2)

#### US-001: Provider/Model Instructions (Slimmed)
**Description:** As an AI engineer, I want provider-specific and model-specific instruction files so that each model receives optimized prompts that match its strengths.

**Note:** Slimmed from original scope. US-010 already shipped the core mechanism (layered prompts, AGENT.md reading, section headers, `instructions_override`). This story adds the **content layer** — provider/model-specific `.md` files and user override resolution.

**Acceptance Criteria:**
- [ ] Built-in instructions shipped in `<package>/instructions/` (e.g., `ollama.md`, `openai.md`, `glm-4.7.md`)
- [ ] User instructions in `~/.nano-agent/instructions/` override built-in files of same name
- [ ] User can pass `instructions="my-custom"` parameter to load a named instruction set
- [ ] Resolution order: explicit param > workspace AGENT.md > user custom > model-specific > provider-level > base prompt
- [ ] Instruction files use Markdown with optional YAML frontmatter for metadata
- [ ] Builds on `build_layered_prompt()` and `instructions_override` from US-010
- [ ] All existing tests pass with no regressions

#### US-005: Smart Model Routing
**Description:** As an AI engineer, I want nano-agent to automatically select the best available model based on a configurable tier mapping so that I don't have to specify the model every time.

**Acceptance Criteria:**
- [ ] New `model="auto"` option triggers smart routing
- [ ] 3-tier configurable mapping with defaults:
  - Heavy: `zai/glm-4.7` (complex, multi-file, architecture)
  - Standard: `lmstudio/qwen3-coder-next` (moderate, single-module)
  - Light: `ollama/qwen3-coder:30b` (simple, single-file)
- [ ] User configures tier mapping in `~/.nano-agent/config.yaml` under `routing:` section
- [ ] Routing respects provider availability via Health Check (US-002) — skips unavailable, tries next in tier
- [ ] Applies correct instruction set via US-001 for the selected model
- [ ] User selects tier explicitly with `model="auto:heavy"`, `model="auto:light"`, etc.
- [ ] Response includes `routing_decision: {tier, model, reason}`
- [ ] Explicit `model="gpt-5-mini"` always overrides routing
- [ ] Tests for tier selection, availability fallback, and explicit override

#### US-006: Agent Pipeline (Chaining)
**Description:** As an AI engineer, I want to chain multiple agents in a pipeline where each agent's output feeds into the next so that I can automate multi-step workflows.

**Acceptance Criteria:**
- [ ] New MCP tool: `prompt_pipeline(steps=[...])` — separate from `prompt_nano_agent`
- [ ] Each step specifies: `{role, prompt, model, provider, template, instructions}` (model/provider optional → uses routing)
- [ ] Output of step N available as `{prev_output}` variable in step N+1's prompt
- [ ] First step receives `{input}` variable from pipeline-level `input` parameter
- [ ] Provider fallback (US-003) applies per step
- [ ] Each step can use `agent_path` for identity-aware execution (via US-010 infrastructure)
- [ ] Pipeline halts on first step failure — returns partial results array with completed steps + error
- [ ] Response: `{success, steps: [{role, model, result, duration}], total_duration, failed_step_index}`
- [ ] Tests for: 2-step pipeline, 3-step pipeline, mid-pipeline failure, variable passing

---

### Phase 4: Observability & Persistence (v2.3)

#### US-007: Streaming Progress
**Description:** As an AI engineer, I want progress updates during agent execution so that I can debug and monitor long-running tasks.

**Acceptance Criteria:**
- [ ] Progress events emitted during agent execution via MCP notifications
- [ ] Events include: `{event_type, step, tool_name, elapsed_seconds, tokens_used}`
- [ ] Event types: `agent_start`, `tool_call_start`, `tool_call_end`, `turn_complete`, `agent_complete`
- [ ] Does not break existing synchronous response flow (events are supplementary)
- [ ] Web dashboard (`nano-web`) shows real-time progress for running agents
- [ ] Works correctly with parallel execution (events tagged with agent/task ID)
- [ ] Tests for event emission, ordering, and parallel isolation

#### US-008: Git-Aware Tools
**Description:** As an AI engineer, I want agents to have git tools so that they can inspect repo state and commit their changes autonomously.

**Acceptance Criteria:**
- [ ] 4 new agent tools: `git_status()`, `git_commit(message)`, `git_branch(name)`, `git_diff()`
- [ ] Tools use `@function_tool` decorator (cross-provider compatible, like existing 6 tools)
- [ ] Workspace-aware: all git operations run in agent's workspace directory
- [ ] Always included in default tool set (alongside existing 6 tools → total 10)
- [ ] Safety guards: no `--force` push, no main/master branch deletion, no `reset --hard`
- [ ] `git_commit` requires a message (cannot be empty)
- [ ] Tests for each git operation and each safety guard

#### US-009: Agent Memory
**Description:** As an AI engineer, I want agents to remember what they did and learned in a project so that they can resume and build on previous work instead of starting from scratch.

**Acceptance Criteria:**
- [ ] Agent execution history stored per-project: `{workspace}/.nano-agent/memory/history.jsonl`
- [ ] Each execution appended as a JSONL entry: `{timestamp, prompt, model, tools_used, files_modified, result_summary}`
- [ ] Extracted project context stored as: `{workspace}/.nano-agent/memory/context.md`
- [ ] Context includes: discovered file structure, patterns, tech stack, key decisions
- [ ] Global memory stored at `~/.nano-agent/memory/global.md` for cross-project patterns
- [ ] Agent's system prompt includes relevant memory context (last N executions + context.md)
- [ ] Memory injected as a labeled section: `## Project Memory` (between instructions and workspace context)
- [ ] Memory size capped (configurable, default: last 10 executions + 2000 chars context)
- [ ] New `memory: false` parameter to disable memory for a single execution
- [ ] Tests for: memory write, memory read, memory injection into prompt, size cap, disable flag

---

## Functional Requirements

### Core MCP Interface

- **FR-1**: `prompt_nano_agent` gains optional parameters: `instructions`, `template`, `template_vars`, `providers`, `memory`
- **FR-2**: New MCP tool `check_providers()` returns provider health status
- **FR-3**: New MCP tool `prompt_pipeline(steps=[...])` for agent chaining
- **FR-3.5**: ~~New MCP tool `launch_agent()` deploys an agent with identity from `agent_path/AGENT.md`~~ SHIPPED (PR #7)
- **FR-4**: All new parameters are backward-compatible (existing calls work unchanged with zero config)

### Instruction System

- **FR-5**: Built-in instructions at `<package>/instructions/{provider}.md` and `<package>/instructions/{model}.md`
- **FR-6**: User instructions at `~/.nano-agent/instructions/` (override built-in of same name)
- **FR-7**: Workspace instructions at `{workspace}/AGENT.md` (highest priority after explicit `instructions` param)
- **FR-8**: Resolution: explicit param > workspace AGENT.md > user custom > model > provider > base prompt
- **FR-9**: Layers concatenated with section headers (`## Base Instructions`, `## Provider: X`, etc.)
- **FR-10**: YAML frontmatter parsed for metadata; body is the instruction text

### Provider Resilience

- **FR-11**: Health check queries all 5 providers concurrently using `httpx.AsyncClient`
- **FR-12**: Fallback chain iterates providers in order, skipping known-down via health check
- **FR-13**: Default fallback: `zai/glm-4.7` → `lmstudio/qwen3-coder-next` → `ollama/qwen3-coder:30b`
- **FR-14**: Each fallback attempt logged with reason for failure in response metadata

### Templates

- **FR-15**: Built-in templates stored as `.md` files with YAML frontmatter (name, description, required_vars, instructions)
- **FR-16**: Template variables use `{variable_name}` syntax, substituted from `template_vars` dict
- **FR-17**: Templates auto-load instruction sets via frontmatter `instructions:` field
- **FR-18**: 6 shipped templates: tdd, implement-feature, code-review, refactor, debug, document

### Routing

- **FR-19**: 3-tier configurable mapping: heavy → standard → light
- **FR-20**: Tier defaults: heavy=`zai/glm-4.7`, standard=`lmstudio/qwen3-coder-next`, light=`ollama/qwen3-coder:30b`
- **FR-21**: User configures via `~/.nano-agent/config.yaml` routing section
- **FR-22**: Routing respects provider availability (falls to next model in same tier)

### Pipeline

- **FR-23**: Pipeline steps execute sequentially (not in parallel)
- **FR-24**: Each step is a full agent execution with its own tools, instructions, and fallback
- **FR-25**: `{prev_output}` variable contains the `result` field from the previous step
- **FR-26**: Pipeline halts on first step failure, returns array of step results including partial

### Git Tools

- **FR-27**: 4 new `@function_tool` tools: `git_status`, `git_commit`, `git_branch`, `git_diff`
- **FR-28**: Safety guards enforced at tool level (reject force-push, main deletion, hard reset)
- **FR-29**: Included in default tool set for all agents

### Agent Memory

- **FR-30**: Per-project memory at `{workspace}/.nano-agent/memory/`
- **FR-31**: Global memory at `~/.nano-agent/memory/global.md`
- **FR-32**: History as JSONL (append-only), context as Markdown (updated after each execution)
- **FR-33**: Memory injected into system prompt as `## Project Memory` section
- **FR-34**: Size cap: last 10 executions + 2000 chars context (configurable)

---

## Non-Goals (Out of Scope for v2.0)

- **NG-1**: Multi-agent real-time collaboration (agents messaging each other during execution)
- **NG-2**: GUI-based workflow builder (web dashboard stays read-only)
- **NG-3**: Custom tool plugins (user-defined `@function_tool` — existing tools suffice)
- **NG-4**: Model fine-tuning or training integration
- **NG-5**: Cloud deployment or hosted service (remains a local MCP server)
- **NG-6**: Breaking changes to existing `prompt_nano_agent` interface
- **NG-7**: Token/cost budget enforcement (deprioritized — primarily local LLM usage)
- **NG-8**: Sandboxed Docker execution (not needed for current workflow)
- **NG-9**: Result caching (replaced by Agent Memory, which is richer)

---

## Technical Considerations

### Architecture

```
MCP Client (Claude Code, Gemini, etc.)
    │
    ▼
FastMCP Server (__main__.py)
    │
    ├── prompt_nano_agent()      ← existing + new params (instructions, template, providers, memory)
    ├── check_providers()        ← new (Phase 1)
    ├── launch_agent()           ← new (Phase 1) — identity-aware agent execution
    └── prompt_pipeline()        ← new (Phase 3)
         │
         ▼
    ┌─────────────────────┐
    │ Instruction Loader   │ ← 4-layer resolution with section headers
    │ Template Engine      │ ← variable substitution + instruction binding
    │ Provider Router      │ ← tier mapping + health check + fallback
    │ Memory Manager       │ ← read/write project + global memory
    └─────────────────────┘
         │
         ▼
    ProviderConfig.create_agent()
         │
         ▼
    OpenAI Agent SDK (Runner.run)
         │
         ├── 6 existing tools (read, write, edit, list, info, bash)
         └── 4 new git tools (status, commit, branch, diff)
```

### Key Files to Modify/Create

| File | Changes |
|------|---------|
| `constants.py` | Add routing defaults, template/instruction paths, memory config |
| `data_types.py` | Extend `PromptNanoAgentRequest` with: instructions, template, template_vars, providers, memory. Add `LaunchAgentRequest` model |
| `nano_agent.py` | Wire instruction loader, fallback chain, memory injection. Add `launch_agent()` function |
| `nano_agent_tools.py` | Add 4 git `@function_tool` definitions |
| `provider_config.py` | Expose `check_all_providers_async()` as standalone method |
| `__main__.py` | Register `check_providers`, `launch_agent`, and `prompt_pipeline` MCP tools |
| **NEW** `modules/instructions.py` | Instruction loader with 4-layer resolution + section headers |
| **NEW** `modules/templates.py` | Template engine with YAML frontmatter + variable substitution |
| **NEW** `modules/routing.py` | 3-tier configurable model routing |
| **NEW** `modules/pipeline.py` | Sequential agent pipeline orchestration |
| **NEW** `modules/memory.py` | Agent memory: history (JSONL) + context (MD) + injection |
| **NEW** `modules/agent_identity.py` | Agent identity loader: read AGENT.md from agent_path, build layered prompt |
| **NEW** `instructions/` | Built-in `.md` files: ollama.md, openai.md, anthropic.md, zai.md, lmstudio.md, glm-4.7.md, qwen3-coder.md |
| **NEW** `templates/` | Built-in template `.md` files: tdd.md, implement-feature.md, code-review.md, refactor.md, debug.md, document.md |

### Dependencies

- No new external dependencies for Phase 1-3 (uses stdlib + existing httpx + PyYAML for config)
- PyYAML may already be a transitive dependency — verify before adding
- All features must work with existing OpenAI Agent SDK `Runner.run()` interface

### Backward Compatibility

All new parameters are optional with sensible defaults:
- `instructions=None` → auto-load based on provider/model (enhanced behavior, not breaking)
- `template=None` → no template (current behavior)
- `providers=None` → use single `provider` parameter (current behavior)
- `memory=True` → enabled by default (additive, does not change outputs for new workspaces with no memory)

### User Configuration Directory

```
~/.nano-agent/
├── config.yaml              ← routing tier mapping, memory limits
├── instructions/            ← user custom instruction .md files
├── templates/               ← user custom template .md files
└── memory/
    └── global.md            ← cross-project memory
```

### Workspace Memory Directory

```
{workspace}/
├── AGENT.md                 ← project-level instructions (auto-detected)
└── .nano-agent/
    └── memory/
        ├── history.jsonl    ← execution history (append-only)
        └── context.md       ← extracted project context
```

---

## Release Phases & Priority

### Phase 1: Foundations (v2.0) — SHIPPED
| Priority | Feature | Complexity | Dependencies | Story | Status |
|----------|---------|------------|--------------|-------|--------|
| 1 | Agent Identity (launch_agent) | Low | None | US-010 | Shipped (PR #7) |
| — | Bash Tool Rename + 30K Output + Persistent CWD | Low | None | — | Shipped (PR #1) |

### Phase 2: Resilience & Productivity (v2.1)
| Priority | Feature | Complexity | Dependencies | Story | Status |
|----------|---------|------------|--------------|-------|--------|
| 2 | Provider Health Check | Low | None | US-002 | Shipped |
| 3 | Provider Fallback Chain | Medium | US-002 | US-003 | Backlog |
| 4 | Execution Templates | Medium | US-010 (shipped) | US-004 | Backlog |

### Phase 3: Intelligence & Orchestration (v2.2)
| Priority | Feature | Complexity | Dependencies | Story | Status |
|----------|---------|------------|--------------|-------|--------|
| 5 | Provider/Model Instructions (Slimmed) | Low-Medium | US-010 (shipped) | US-001 | Backlog |
| 6 | Smart Model Routing | Medium | US-001, US-002 | US-005 | Backlog |
| 7 | Agent Pipeline | High | US-010 (shipped), US-003 | US-006 | Backlog |

### Phase 4: Observability & Persistence (v2.3)
| Priority | Feature | Complexity | Dependencies | Story | Status |
|----------|---------|------------|--------------|-------|--------|
| 8 | Streaming Progress | Medium | None | US-007 | Backlog |
| 9 | Git-Aware Tools | Medium | None | US-008 | Backlog |
| 10 | Agent Memory | Medium-High | None | US-009 | Backlog |

---

## Dependency Graph

```
SHIPPED (v2.0)          Phase 2 (v2.1)            Phase 3 (v2.2)           Phase 4 (v2.3)
──────────────          ──────────────            ──────────────           ──────────────

┌──────────────┐     ┌──────────────────┐
│ US-010 ✅    │────▶│ US-004 Templates │
│ Agent ID     │──┐  └──────────────────┘
└──────────────┘  │                           ┌──────────────────┐
                  │                        ┌─▶│ US-006 Pipeline  │
                  │                        │  └──────────────────┘
                  │  ┌──────────────────┐  │
                  └─▶│ US-001* Slim     │──┘
                  ┌─▶│ Provider .md's   │
                  │  └──────────────────┘
                  │  ┌──────────────────┐
                  └─▶│ US-005 Routing   │
                     └──────────────────┘
              ┌──────────────┐     ┌──────────────────┐
              │ US-002 ✅    │────▶│ US-003 Fallback  │──┐
              │ Health Check │     └──────────────────┘  │
              └──────────────┘                           │
                                   (US-006 also needs)───┘
                                                          ┌────────────┐
              INDEPENDENT (anytime)                       │ US-007     │
              ─────────────────────                       │ Streaming  │
              US-007 Streaming                            ├────────────┤
              US-008 Git Tools                            │ US-008     │
              US-009 Memory                               │ Git Tools  │
                                                          ├────────────┤
                                                          │ US-009     │
                                                          │ Memory     │
                                                          └────────────┘

* US-001 slimmed: only provider/model .md files + resolution chain.
  Core mechanism (layered prompts, AGENT.md, instructions_override) shipped in US-010.

Unblocked now: US-003, US-004, US-007, US-008, US-009 (5 of 7 remaining)
Blocked:       US-005 (needs US-001+US-002), US-006 (needs US-003)
```

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Agent output quality | Higher task completion rate with instructions vs. without | A/B benchmark on 10 standard tasks |
| Provider failure recovery | Zero wasted cycles from provider downtime | Track `provider_attempts` in responses |
| Template reuse | 80% of executions use a template after Phase 2 | Count `template` parameter usage |
| Memory effectiveness | Agents reference previous work in 50%+ of returning sessions | Check memory injection in prompts |
| Community adoption | 5+ community instruction/template contributions | GitHub PRs with `.md` files |

---

## Open Questions (Resolved)

| Question | Decision | Rationale |
|----------|----------|-----------|
| Instruction file format | Markdown + optional YAML frontmatter | Industry standard across Claude, Copilot, AGENTS.md |
| Instruction layering | Concatenate with section headers | Industry best practice. Clear, debuggable, no contradictions. |
| Workspace instructions | `{workspace}/AGENT.md` auto-detected | Per-project scoping via workspace parameter. No conflicts. |
| Budget priority | Deprioritized | Primarily local LLMs (free). Simple `max_turns` exists already. |
| Pipeline error handling | Halt + partial results | User decides next action. Safer than skip-and-continue. |
| Caching vs Memory | Memory replaces caching | Richer: history + context + cross-project. Subsumes cache benefit. |
| Sandbox | Removed | Not needed. Controlled workspaces + local LLMs. |
| Git tools availability | Always included (not opt-in) | Safety guards prevent destructive operations. |
| Routing method | Configurable tier mapping (not heuristic) | Predictable, user-controlled, simple. |
| Fallback default | GLM-4.7 → Qwen-Next → Qwen-Coder | User's preferred model priority. |

| Template variable validation | Error before execution, list missing vars + descriptions | Error: "Template 'tdd' requires: {target_file} (Path to implement), {test_file} (Path to test file). Missing: {test_file}". No tokens wasted. |
| Memory context update | Both: auto-extract + agent self-reflection | Post-processing extracts facts, then optionally agent reflects. Most comprehensive. |
| Config file format | YAML (`~/.nano-agent/config.yaml`) | More readable for nested config (routing tiers, memory limits). DevOps standard (Docker, K8s, pytest). |

## Remaining Open Questions

None — all design decisions resolved during PRD alignment.
