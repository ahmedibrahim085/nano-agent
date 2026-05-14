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

#### US-012: Ollama Cloud Provider + Live Model Discovery & Search
**Description:** As an AI engineer, I want to call Ollama Cloud's hosted high-parameter models (`gpt-oss:120b-cloud`, `qwen3-coder:480b-cloud`, `deepseek-v3.1:671b-cloud`, future additions) directly from nano-agent — and discover/filter the current catalog at runtime so I can find the right family + size without waiting for a code release every time Ollama publishes a new model.

**Motivation:** Today nano-agent has six providers; the `ollama` provider routes to localhost only. Ollama's cloud catalog at `https://ollama.com` is a separate first-party endpoint hosting datacenter-scale models behind a Bearer token — datacenters where 671B-parameter open models actually fit. Hardcoding the catalog in `constants.py` (as we do for every other provider) is brittle here because Ollama updates the cloud catalog frequently — the registry goes stale fast. So this story bundles three pieces: **(a)** the provider plumbing, **(b)** live model discovery via `/v1/models`, and **(c)** a search/filter MCP tool that lets a user (or agent) find a model by family + size without knowing the exact ID.

**Acceptance Criteria:**

*Provider plumbing*
- [ ] New provider `ollama_cloud` registered in `PROVIDER_REQUIREMENTS`, `AVAILABLE_MODELS`, `MODEL_INFO`, and the `Literal` provider tuple in `data_types.py`
- [ ] Endpoint: `https://ollama.com/v1/` (OpenAI-compatible) wired via `OpenAIChatCompletionsModel` — same pattern as `ollama`, `lmstudio`, `qwen`
- [ ] Authentication: Bearer token from env var `OLLAMA_API_KEY` (matches Ollama's own convention); missing key → graceful `down` status, not a crash
- [ ] Health check (`check_providers`) extended for `ollama_cloud`: verifies API key set + endpoint reachable via `/v1/models`
- [ ] Bootstrap model list in `constants.py` covering today's known cloud models — `gpt-oss:120b-cloud`, `gpt-oss:20b-cloud`, `qwen3-coder:480b-cloud`, `deepseek-v3.1:671b-cloud` — used **only** as fallback when live discovery fails
- [ ] Cross-provider tool compatibility: existing 13 `@function_tool` agent tools (read_file, write_file, bash, etc.) work against Ollama Cloud models with no per-provider hacks
- [ ] Token tracking entries in `token_tracking.py` for known cloud models (pricing initially 0.00/0.00 — preview is free; update when Ollama publishes per-token pricing)

*Live model discovery*
- [ ] New helper `ProviderConfig.discover_models(provider: str) -> list[str]` that queries the provider's `/v1/models` endpoint and returns the live catalog
- [ ] Per-provider opt-in via a `supports_dynamic_discovery: bool` flag — initially `True` for `ollama_cloud`, `ollama`, `lmstudio`, `openai`; `False` for `zai`, `qwen`, `anthropic` (until proven safe)
- [ ] Result cached in-process with configurable TTL (default 300s, env var `NANO_AGENT_MODEL_DISCOVERY_TTL_SECONDS`)
- [ ] `check_providers()` consults the cache, refreshing if expired; the `available_models` field reflects the live catalog, not just the hardcoded list
- [ ] Graceful degradation: if `/v1/models` times out or 5xxs, fall back to the bootstrap list in `constants.py` and surface `discovery_error` in response metadata
- [ ] Discovery never blocks an agent call — only `check_providers()` and `find_models()` trigger network fetches

*Model search MCP tool*
- [ ] New MCP tool `find_models(family: str | None = None, size: str | None = None, provider: str | None = None) -> list[ModelMatch]`
- [ ] `family` matches case-insensitive substring against the part of the model ID before `:` (the family segment). Examples:
  - `find_models(family="qwen3")` → returns all qwen3-* models across providers (local + cloud)
  - `find_models(family="gpt-oss")` → returns gpt-oss:20b, gpt-oss:120b, gpt-oss:20b-cloud, gpt-oss:120b-cloud
- [ ] `size` matches case-insensitive substring of the size segment (the part after `:`, before any `-cloud` / EOL suffix). Examples:
  - `find_models(size="27b")` → all 27B models
  - `find_models(family="qwen3.6", size="27")` → matches a `qwen3.6:27b` (or `qwen3.6:27b-cloud`) entry — exactly the use case the user described
- [ ] `provider` (optional) restricts results to one provider; otherwise searches across all discovery-enabled providers plus their hardcoded entries
- [ ] Each result entry: `{provider, model, source: "live" | "bootstrap", capabilities_known: bool}` — `capabilities_known` tells callers whether `MODEL_CAPABILITIES` has a tuned entry (i.e. whether tool support / max_tokens / temperature defaults are reliable for this model)
- [ ] Empty filter `find_models()` returns the full catalog across all discovery-enabled providers (capped to 200 entries to bound output size)
- [ ] `mcp_logging` emits `models.discover` (provider, count, source, elapsed_s) and `models.find` (query, result_count, elapsed_s) events

*Tests*
- [ ] `ollama_cloud` provider: end-to-end agent run against the live endpoint (or mocked) — write file → read file → report
- [ ] Health check: API key missing → `status=down`; key present + endpoint reachable → `status=up` with live model list
- [ ] Discovery: mocked `/v1/models` response returns expected models; TTL cache hits; cache miss after TTL; `/v1/models` failure falls back to bootstrap list with `discovery_error` surfaced
- [ ] `find_models`: family-only filter, size-only filter, both, neither, with/without provider scoping, no-match case
- [ ] Capabilities fallback: unknown model reports `capabilities_known=false` and uses `DEFAULT_MODEL_CAPABILITY`

**Operational recommendations (added during planning review):**
- [ ] **HTTP 429 rate-limit handling**: Ollama Cloud's preview tier may rate-limit; on 429 response (from `/v1/models` discovery, `/v1/chat/completions`, or any cloud endpoint), retry with exponential backoff (250ms → 500ms → 1s; max 3 attempts) before surfacing as failure. Retry behavior controllable via `NANO_AGENT_RETRY_ON_429={true|false}` (default `true`)
- [ ] **Deep health probe**: when `OLLAMA_API_KEY` is present, `check_providers()` optionally runs a tiny chat completion against the cheapest available cloud model (likely `gpt-oss:20b-cloud`) to distinguish "API key valid + endpoint healthy" from "API key present but rejected / quota-exceeded". Controlled by a `deep_health: bool = False` parameter — opt-in because it costs a real request.
- [ ] **Auth-failure error mapping**: `401 Unauthorized` from cloud → `status=down`, `error="Invalid OLLAMA_API_KEY"`; `403 Forbidden` → `error="API key valid but unauthorized for this model"`; both surfaced cleanly in `check_providers` output

**Open Design Questions (resolve during spec phase):**
- Should `find_models` also surface context-window and parameter-count metadata when the provider's `/v1/models` response includes them?
- Bootstrap list location: stay in `constants.py` (current pattern) or move to a separate `bootstrap_models.json` so it can be updated without a code release?
- Should `check_providers()` force a discovery refresh, or respect the TTL cache? (Probably force — health check is a deliberate user action.)
- For providers without `/v1/models` (e.g. Anthropic), `find_models` falls back to hardcoded `AVAILABLE_MODELS` — confirm this is the right behavior or whether we should hide them entirely from search results.
- Deep-health-probe model selection: hardcoded cheapest model in bootstrap list, or auto-derived from the discovery result's lowest-cost entry?

#### US-013: Multi-Model Fan-Out Execution
**Description:** As an AI engineer, I want to send the same prompt to multiple `(model, provider)` combinations in a single MCP call and receive all of their responses with per-model timing and cost data, so I can compare answers side-by-side without orchestrating N separate calls from the client.

**Motivation:** Today's parallelism is client-orchestrated — the MCP caller issues N concurrent `prompt_nano_agent` calls. That works (ContextVars guarantee isolation), but the comparison logic lives in the caller and the response shape is "N separate tool results" rather than "one structured comparison". A first-class fan-out tool returns a typed `list[ModelResult]` that's iterable, sortable, and trivially serializable. **Fan-out is also the foundational primitive** that US-014 (Race) and US-015 (Ensemble) build on — shipping it first creates shared infrastructure both depend on.

**Acceptance Criteria:**

*Tool surface*
- [ ] New MCP tool: `prompt_models_parallel(prompt: str, model_specs: list[ModelSpec], workspace?: str = None, isolate_workspaces: bool = False) -> ParallelResult`
- [ ] `ModelSpec` schema: `{model: str, provider: str, model_settings?: dict, max_turns?: int = None, agent_path?: str = None}` — `agent_path` allows mixing in `launch_agent`-style identities per spec
- [ ] `ModelResult` schema: `{model, provider, success, result?, error?, error_type?, elapsed_s, turn_count?, token_usage?, cost?, capabilities_known: bool}`
- [ ] `ParallelResult` schema: `{results: list[ModelResult], started_at, ended_at, total_wall_elapsed_s, total_token_usage, fastest_spec_index?: int, cheapest_spec_index?: int, deduped_specs: list[int]}` — `fastest_spec_index` and `cheapest_spec_index` index into `results` (None if no spec succeeded); `deduped_specs` lists indices of duplicate specs that were silently dropped

*Pre-flight validation (recommendation: added during planning review)*
- [ ] Validate each `ModelSpec` before any spec runs: provider must be in the `Literal[...]` tuple from `data_types.py`; model not in `MODEL_CAPABILITIES` is allowed but the spec gets `capabilities_known=False` in its eventual ModelResult
- [ ] Invalid specs fail fast with a structured `ValidationError` response — zero token cost incurred when input is malformed
- [ ] **Deduplication**: exact duplicate specs (same model+provider+settings) deduped silently with `deduped_specs` reporting the dropped indices — prevents accidental double-billing

*Concurrency mechanics*
- [ ] One failing spec does NOT cancel the others — every spec runs to completion (or its `max_turns` cap) independently
- [ ] Uses `asyncio.gather(..., return_exceptions=True)` so exceptions become structured failures in their `ModelResult`, not thrown out
- [ ] Each spec gets its own ContextVar copy (workspace, bash CWD, bg PIDs) — reuses existing isolation infrastructure
- [ ] `isolate_workspaces=False` (default): all specs share the requested `workspace` (good for code review where they all read the same files)
- [ ] `isolate_workspaces=True`: each spec gets a sandboxed subdir `{workspace}/.nano-agent/parallel/{spec_index}/` to prevent file-write collisions
- [ ] Concurrency cap configurable via `NANO_AGENT_PARALLEL_MAX_CONCURRENT` (default 4); excess specs queue and start as others finish

*Observability*
- [ ] `mcp_logging` events: `mcp.prompt_models_parallel.start` (spec_count, dedup_count), `.validation_failed` (errors), `.spec_start` (spec_index, model, provider), `.spec_end` (spec_index, success, elapsed_s), `.end` (total_elapsed_s, success_count, failure_count, fastest_spec_index, cheapest_spec_index)

*Tests*
- [ ] Two specs both succeed → wall ≈ max(per_spec), not sum; `fastest_spec_index` and `cheapest_spec_index` populated correctly
- [ ] One fails one succeeds → both ModelResults returned; `fastest_spec_index` points to the successful one (failed specs ineligible)
- [ ] `isolate_workspaces=true` sandboxes each spec's file writes
- [ ] Concurrency cap honored (6 specs, cap=2 → only 2 concurrent at a time)
- [ ] Pre-flight validation rejects invalid provider before any spec runs (zero token cost)
- [ ] Deduplication: same spec listed twice → only one runs, `deduped_specs` reports the dropped index

**Open Design Questions (resolve during spec phase):**
- Streaming partial results before all specs finish? Coupled to US-007 (Streaming Progress); defer until that ships.
- Optional `max_total_cost_usd` parameter that cancels remaining specs once exceeded?
- Should the response include a richer correctness ranking (judge-model best-of) at server side, or defer that to US-015?

#### US-014: Multi-Model Race (First-Success Wins)
**Description:** As an AI engineer, I want to dispatch the same prompt to multiple providers in parallel and receive only the **first successful** response — with the slower or failing providers automatically cancelled — so I get the lowest possible latency for time-sensitive workflows without writing fallback logic.

**Motivation (real-world driver):** Providers fail unpredictably. During this project's GLM-5.1 timeout investigation (traces preserved in `~/.nano-agent/logs/mcp-actions.log`), we confirmed that a single-provider strategy is brittle: GLM-5.1 with thinking-on can take 120s+ on tasks where `gpt-5-mini` finishes in 15s — and either can hit transient errors that look indistinguishable from real timeouts. US-003's sequential fallback wastes the wait. **Race turns "fail-and-retry" into "race-and-take-winner"**, cutting tail latency from "worst-case provider" to "best-case provider in flight" — a strict improvement over both single-provider and sequential-fallback strategies.

**Acceptance Criteria:**

*Tool surface*
- [ ] New MCP tool: `prompt_models_race(prompt: str, model_specs: list[ModelSpec], workspace?: str = None, max_wait_s: float = 300.0, per_spec_timeout_s?: float = None, skip_known_down: bool = True, preset?: str = None) -> RaceResult`
- [ ] `RaceResult` schema: `{winner: ModelResult | None, losers: list[ModelResult], total_wall_elapsed_s, race_aborted_reason?: str}` — `winner` is the first spec to return `success=true`; each loser carries `cancelled: bool`, `cancelled_at_elapsed_s?`, `skipped_provider_down?: bool`

*Cancellation & timing*
- [ ] Cancellation mechanic: `asyncio.wait(..., return_when=FIRST_COMPLETED)` loop — on first `success=true` result, remaining tasks get `task.cancel()`
- [ ] Cancelled tasks complete their `finally` blocks (existing `_cleanup_background_processes` flow) so background processes spawned by losers are killed
- [ ] If ALL specs fail (no success), returns `winner=None` + full `losers` list — caller inspects each failure
- [ ] `max_wait_s` caps the **whole race**; `per_spec_timeout_s` (optional) caps **each individual spec** — both apply, whichever hits first wins

*Health-check integration (recommendation: added during planning review)*
- [ ] Before dispatching, consult `check_providers()` cache (US-002, shipped) and skip specs whose provider is currently `status=down`. Controlled by `skip_known_down: bool = True` parameter.
- [ ] Skipped specs appear in `losers` with `skipped_provider_down=true` and `error="provider known down at race start"` — they still count toward the race outcome (if all specs are skipped, `winner=None` and `race_aborted_reason="all_providers_down"`)

*Reliability preset (recommendation: added during planning review)*
- [ ] **`preset="reliability"` shortcut**: server-side default 3-way race using a curated combo (initial: `glm-5.1/zai`, `gpt-5-mini/openai`, `qwen3-coder:30b/ollama`). Configurable via `NANO_AGENT_RACE_PRESET_RELIABILITY` env var (JSON list of ModelSpec)
- [ ] Caller can override with their own `model_specs` — `preset` and `model_specs` are mutually exclusive (passing both raises ValidationError)

*Cleanup & observability*
- [ ] Builds on US-013's shared infrastructure (ContextVar isolation, concurrency cap, `ModelResult` schema, validation, deduplication)
- [ ] Files written by cancelled specs in their workspace are NOT cleaned up (intentional — easy debugging); background processes ARE killed
- [ ] `mcp_logging` events: `mcp.prompt_models_race.start`, `.skip_down` (spec_index, provider), `.spec_start`, `.winner` (spec_index, model, provider, elapsed_s), `.cancel` (spec_index, cancelled_at_elapsed_s), `.timeout`, `.end`

*Tests*
- [ ] First succeeds fast → winner=first; remaining losers have `cancelled=true`
- [ ] First fails, second succeeds → winner=second; first is in losers with error
- [ ] All fail → `winner=None`
- [ ] `max_wait_s` timeout cancels stragglers
- [ ] `per_spec_timeout_s` cancels just-the-slow-one (other specs unaffected)
- [ ] `skip_known_down=true` excludes specs whose provider's health check is `down`; all-down → `race_aborted_reason="all_providers_down"`
- [ ] `preset="reliability"` expands to the configured spec list; caller-provided specs override preset
- [ ] Cancellation kills background processes spawned by losers (regression guard against orphaned bash subprocesses)

**Open Design Questions (resolve during spec phase):**
- Does a partial agent output (max_turns exceeded but partial result available) count as "success" for race purposes? Probably not — race semantics should mean `success=true` from Runner.run.
- Should the `reliability` preset's model list be hardcoded in `constants.py` or auto-derived from `check_providers().status=up` providers at server startup?
- Should we expose a "warm winner" optimization — remember which spec won the last K races for similar prompts and bias scheduling order toward it?

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

#### US-015: Multi-Model Ensemble (Reduce to One Answer)
**Description:** As an AI engineer, I want to dispatch the same prompt to multiple models and have nano-agent **automatically combine their responses into a single reduced answer** (via consensus, judge-based ranking, or synthesis), so I get production-grade reliability through cross-model agreement without writing a separate aggregation layer in my client.

**Motivation:** For high-stakes outputs (code review verdicts, security analysis, refactor proposals), one model's answer is a single point of failure. Asking N models and reducing catches hallucinations and surfaces real agreement. Today this requires N calls + custom reducer code in the client — error-prone, not reusable, and the reducer often duplicates LLM-as-judge logic that belongs in shared infrastructure.

**Acceptance Criteria:**
- [ ] New MCP tool: `prompt_models_ensemble(prompt: str, model_specs: list[ModelSpec], reducer: ReducerSpec, workspace?: str = None) -> EnsembleResult`
- [ ] `ReducerSpec` is a tagged union with three implementations:
  - [ ] **`{mode: "consensus", min_agreement: float = 0.7, embedding_model?: str}`** — cluster responses via embedding similarity; return the centroid of the largest cluster if cluster_size/total ≥ `min_agreement`; otherwise return `agreement=false` and all responses
  - [ ] **`{mode: "best", judge_model: str, judge_provider: str, rubric: str}`** — send all responses + the rubric to a judge model; ask it to pick the best; return winner + judge's rationale
  - [ ] **`{mode: "merge", merge_model: str, merge_provider: str, merge_prompt: str}`** — send all responses to a synthesizer model that unifies them into one response
- [ ] `EnsembleResult` schema: `{reduced: str | None, reducer_metadata: dict, all_responses: list[ModelResult], total_elapsed_s, total_cost_usd}` — `reducer_metadata` contains mode-specific fields (cluster sizes for consensus, judge rationale for best, synthesis notes for merge)
- [ ] Two-stage execution: stage 1 dispatches specs in parallel (reusing US-013); stage 2 runs the reducer (sequential, on the result set)
- [ ] Reducer failure is non-fatal: if the reducer model fails, returns `reduced=None` + `reducer_error` field + all raw responses still preserved
- [ ] Cost rollup includes the reducer model's tokens — `total_cost_usd` covers both stages
- [ ] `mcp_logging` events: `mcp.prompt_models_ensemble.dispatch_end`, `.reduce_start` (mode), `.reduce_end` (mode, agreement_metric, elapsed_s)
- [ ] Tests: consensus mode with 3 similar responses → returns centroid; consensus with 3 divergent → returns `agreement=false`; best mode → judge selects one with rationale; merge mode → synthesized output references inputs; reducer model fails → graceful degradation with `reducer_error` set

**Operational recommendations (added during planning review):**
- [ ] **`max_total_cost_usd` cost cap**: optional parameter that aborts the ensemble before dispatch if the projected cost (estimated from cached pricing × prompt-size token estimate × spec count) would exceed the cap. Returns `EnsembleResult` with `reduced=None`, `cost_cap_exceeded=true`, and `estimated_cost_usd` so the caller knows how close they were. Default `None` = no cap (current behavior).
- [ ] **`abstain_on_disagreement` for consensus mode**: `{mode: "consensus", min_agreement: 0.7, abstain_on_disagreement: bool = False}`. When `true` and no agreement reached, returns `reduced=None` and `reducer_metadata={"abstained": true, "max_cluster_size": N}` — forces the caller to handle ambiguity explicitly instead of receiving an unclear "here are all 3 different answers" payload that they then have to disambiguate.
- [ ] **Structured-output ensemble**: if all responses follow a JSON schema (i.e. `model_specs` all used the same `response_format`), the reducer applies a schema-aware merge — per-field consensus across responses, surfacing per-field disagreement metadata. Avoids the "stringly-typed consensus" trap where two semantically-identical answers fail similarity matching due to surface-text differences.

**Open Design Questions (resolve during spec phase):**
- Embedding model for consensus mode: default to `gpt-5-nano` (cheap, available) or a local Ollama embedding (`nomic-embed-text`) when discoverable?
- Should consensus mode have a structural-similarity option (e.g. AST diff for code outputs) in addition to embedding similarity?
- "Best" mode bias: the judge model has its own preferences. Worth a `multi_judge` extension where N judges vote? Defer to v2.4.
- For merge mode: the `merge_prompt` should accept template variables `{response_1}`, `{response_2}`, ... — clean syntax for the implementer.
- Cost-cap estimation accuracy: prompt-size × spec-count is rough — should we use actual token-counting (tiktoken or provider-specific) for cap precision, accepting the small extra latency?

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

#### US-011: Cross-Call Multi-Turn Continuity
**Description:** As an AI engineer using nano-agent via MCP, I want consecutive `prompt_nano_agent` / `launch_agent` calls to share conversation state when I opt in, so that I can have an iterative back-and-forth with a worker agent — refining its previous output, asking follow-up questions, or correcting course — without manually re-embedding the full prior context in every new prompt.

**Motivation:** Today every MCP call is stateless (verified: `PromptNanoAgentRequest` has no session field; `Runner.run` always starts a fresh agent). Users wanting continuity must either (a) include the entire prior thread in each new prompt — token-expensive and fragile — or (b) hand-roll file-based handoff. This story makes opt-in continuity a first-class capability.

**Acceptance Criteria:**
- [ ] New optional `session_id: str` parameter on `prompt_nano_agent` and `launch_agent` (default `None` = stateless one-shot, current behavior preserved)
- [ ] When `session_id` is supplied, the agent loads prior conversation state from a deterministic store, executes the new turn with that history in context, then persists the updated state before returning
- [ ] Stateless path (no `session_id`) remains the default and is fully backward compatible — zero behavior change for existing callers
- [ ] **Two persistence backends, both must pass the same test suite**, selectable via env var `NANO_AGENT_SESSION_BACKEND={file|memory}` (default `file`):
  - [ ] **File backend**: JSONL message log at `~/.nano-agent/sessions/{session_id}/messages.jsonl` — append-only, durable across MCP server restarts
  - [ ] **Memory backend**: in-process `dict[session_id, list[message]]` — zero read latency, cleared on server restart (useful for hot iterative loops where durability isn't needed)
- [ ] Session state stored: full message history (user / assistant / tool_call / tool_result) with timestamps and model/provider used per turn
- [ ] Sliding-window cap on history: default last 50 turns OR 100K tokens (whichever hit first), configurable via env vars
- [ ] On cap overflow: drop oldest turns by default; opt-in model-driven summarization if `NANO_AGENT_SESSION_SUMMARIZE_ON_OVERFLOW=1`
- [ ] `session_id` is opaque to nano-agent — caller is responsible for collision avoidance (UUID v4 or workflow-scoped string recommended)
- [ ] Two new MCP tools: `clear_session(session_id)` wipes one session's state; `list_sessions()` enumerates known sessions with last-touched timestamp, turn count, and rolled-up token usage
- [ ] `mcp_logging` emits structured events: `session.load` (session_id, prior_turns, backend), `session.save` (session_id, total_turns, bytes_written), `session.overflow` (session_id, dropped_turns)
- [ ] Backward-compat check: existing PRs that don't pass `session_id` see identical behavior to today; existing tests pass unchanged
- [ ] Tests: stateless still works (no regression); two sequential calls with same `session_id` share context; concurrent calls with different `session_id`s don't bleed; overflow drops oldest correctly; summarization-on-overflow produces a single condensed system turn; `clear_session` wipes state; `list_sessions` reports accurately; both backends pass identical test suite

**Operational recommendations (added during planning review):**
- [ ] **Session TTL / auto-cleanup**: file-backend sessions auto-expire after `NANO_AGENT_SESSION_TTL_DAYS` (default 30). On every `prompt_nano_agent` invocation, asynchronously sweep `~/.nano-agent/sessions/` and remove sessions whose `last-touched` mtime exceeds the TTL. Memory backend dies with the process so no cleanup needed.
- [ ] **Convenience alias `session_id="latest"`**: resolves to the most-recently-touched session for the current `workspace` (or the calling agent_path, if `launch_agent`). Avoids the "did I save my session ID somewhere?" problem during interactive iteration.
- [ ] **Bulk operations on `clear_session`**: accept either a single `session_id` or `"*"` for wipe-all, plus an optional `older_than_days: int` filter for selective cleanup.

**Open Design Questions (resolve during spec phase):**
- Default backend: `file` (durable) is safer for end-users; `memory` is faster for orchestrators. Which should `NANO_AGENT_SESSION_BACKEND` default to?
- Should `launch_agent` sessions key by `(agent_path, session_id)` so the same session-id under two different agents stays separate?
- Should we expose session-state as MCP resources (`nano-agent://sessions/{id}`) for read-only inspection?
- Should `session_id="latest"` resolve scope by `workspace`, `agent_path`, both, or be configurable per call?

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
- **FR-39**: New provider `ollama_cloud` — OpenAI-compat against `https://ollama.com/v1/`, Bearer auth via `OLLAMA_API_KEY`; wires through existing `OpenAIChatCompletionsModel` (same pattern as `ollama`/`lmstudio`/`qwen`)
- **FR-40**: Live model discovery via `/v1/models` for any provider with `supports_dynamic_discovery=True`; result cached in-process with configurable TTL (default 300s, env var `NANO_AGENT_MODEL_DISCOVERY_TTL_SECONDS`)
- **FR-41**: Graceful fallback to a bootstrap model list in `constants.py` when discovery fails (timeout, 5xx, missing key); failures surfaced as `discovery_error` in response metadata
- **FR-42**: New MCP tool `find_models(family?, size?, provider?)` for cross-provider model search; returns entries with `{provider, model, source, capabilities_known}`

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

### Parallel Execution

- **FR-43**: New MCP tool `prompt_models_parallel(prompt, model_specs)` — fan-out execution; returns per-spec `ModelResult` entries; one failure doesn't cancel siblings
- **FR-44**: Workspace isolation per spec opt-in via `isolate_workspaces` flag; default shares the requested workspace across all specs
- **FR-45**: Concurrency cap configurable via `NANO_AGENT_PARALLEL_MAX_CONCURRENT` (default 4); applies to all three parallel tools (parallel/race/ensemble)
- **FR-46**: New MCP tool `prompt_models_race(prompt, model_specs, max_wait_s)` — first-success-wins; remaining specs cancelled via `task.cancel()`; background processes cleaned up on cancel
- **FR-47**: New MCP tool `prompt_models_ensemble(prompt, model_specs, reducer)` — three reducer modes: `consensus` (embedding clustering with `min_agreement`), `best` (judge model + rubric), `merge` (synthesizer model + merge prompt); reducer failure is non-fatal, raw responses always preserved

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
- **FR-35**: Optional `session_id` parameter on `prompt_nano_agent` and `launch_agent`; absence preserves current stateless behavior
- **FR-36**: Two interchangeable session-persistence backends — file (JSONL at `~/.nano-agent/sessions/{session_id}/messages.jsonl`) and in-process memory dict — selectable via `NANO_AGENT_SESSION_BACKEND={file|memory}`
- **FR-37**: Sliding-window cap on session history (default 50 turns OR 100K tokens, configurable); optional model-driven summarization on overflow via `NANO_AGENT_SESSION_SUMMARIZE_ON_OVERFLOW`
- **FR-38**: `clear_session(session_id)` and `list_sessions()` MCP tools for session lifecycle and inspection

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
| 12 | Ollama Cloud Provider + Model Discovery & Search | Medium-High | US-002 (health check infra) | US-012 | Backlog |
| 13 | Multi-Model Fan-Out Execution | Medium | None (foundational for US-014 / US-015) | US-013 | Backlog |
| 14 | Multi-Model Race (First-Success Wins) ⭐ elevated for production reliability | Low-Medium | US-013 (shared infra), US-002 (health-check skip) | US-014 | Backlog |

### Phase 3: Intelligence & Orchestration (v2.2)
| Priority | Feature | Complexity | Dependencies | Story | Status |
|----------|---------|------------|--------------|-------|--------|
| 5 | Provider/Model Instructions (Slimmed) | Low-Medium | US-010 (shipped) | US-001 | Backlog |
| 6 | Smart Model Routing | Medium | US-001, US-002 | US-005 | Backlog |
| 7 | Agent Pipeline | High | US-010 (shipped), US-003 | US-006 | Backlog |
| 15 | Multi-Model Ensemble (Consensus / Judge / Merge) | High | US-013 (shared infra) | US-015 | Backlog |

### Phase 4: Observability & Persistence (v2.3)
| Priority | Feature | Complexity | Dependencies | Story | Status |
|----------|---------|------------|--------------|-------|--------|
| 8 | Streaming Progress | Medium | None | US-007 | Backlog |
| 9 | Git-Aware Tools | Medium | None | US-008 | Backlog |
| 10 | Agent Memory | Medium-High | None | US-009 | Backlog |
| 11 | Cross-Call Multi-Turn Continuity | High | US-009 (shared persistence layer) | US-011 | Backlog |

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
