"""
Central constants and configuration for the Nano Agent.

This module contains all shared constants, default values, and configuration
used across the nano agent codebase.
"""

from .data_types import ModelCapability

# Default Model Configuration
DEFAULT_MODEL = "gpt-5-mini"  # Efficient, fast, good for most tasks
DEFAULT_PROVIDER = "openai"

# Available Models by Provider
AVAILABLE_MODELS = {
    "openai": ["gpt-5", "gpt-5-mini", "gpt-5-nano", "gpt-4o"],
    "anthropic": [
        "claude-opus-4-1-20250805",
        "claude-opus-4-20250514",
        "claude-sonnet-4-20250514",
        "claude-3-haiku-20240307",
    ],
    "ollama": [
        "gpt-oss:20b",
        "gpt-oss:120b",
        "qwen3-coder:30b",
        "gemma3:27b",
        "magistral:latest",
    ],
}

# Model Display Names and Descriptions
MODEL_INFO = {
    "gpt-5-nano": "GPT-5 Nano - Fastest, best for simple tasks",
    "gpt-5-mini": "GPT-5 Mini - Efficient, fast, good for most tasks",
    "gpt-5": "GPT-5 - Most powerful, best for complex reasoning",
    "gpt-4o": "GPT-4o - Previous generation, proven reliability",
    "claude-opus-4-1-20250805": "Claude Opus 4.1 - Latest Anthropic flagship",
    "claude-opus-4-20250514": "Claude Opus 4 - Powerful reasoning",
    "claude-sonnet-4-20250514": "Claude Sonnet 4 - Balanced performance",
    "claude-3-haiku-20240307": "Claude 3 Haiku - Fast and efficient",
    "gpt-oss:20b": "GPT-OSS 20B - Local open-source model",
    "gpt-oss:120b": "GPT-OSS 120B - Large local model",
    "qwen3-coder:30b": "Qwen3 Coder 30B - Local coding specialist",
    "gemma3:27b": "Gemma3 27B - Google's local model",
    "magistral:latest": "Magistral 24B - Local reasoning model",
    # Z.ai
    "glm-4.7": "GLM-4.7 - Z.ai flagship reasoning model",
    "glm-4.5-air": "GLM-4.5 Air - Z.ai fast model",
    # Qwen Cloud
    "coder-model": "Qwen Coder - Cloud coding specialist (qwen3-coder-plus)",
}

# Provider API Key Requirements
PROVIDER_REQUIREMENTS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "ollama": None,  # No API key needed
    "lmstudio": None,  # No API key needed
    "zai": "Z_AI_API_KEY",  # Z.ai API key
    "qwen": None,  # OAuth file-based auth, not env var
}

# Z.ai Configuration
ZAI_BASE_URL = "https://api.z.ai/api/anthropic"
ZAI_AVAILABLE_MODELS = ["glm-4.7", "glm-4.5-air"]

# Qwen Cloud Configuration
QWEN_BASE_URL = "https://portal.qwen.ai/v1"
QWEN_AVAILABLE_MODELS = ["coder-model"]

# Agent Configuration
MAX_AGENT_TURNS = 20  # Maximum turns in agent loop

# Per-model capabilities registry

# Fallback for unknown models
DEFAULT_MODEL_CAPABILITY = ModelCapability()

MODEL_CAPABILITIES: dict[str, ModelCapability] = {
    # OpenAI
    "gpt-5": ModelCapability(
        temperature=1.0,       # GPT-5 doesn't support custom temperature
        max_tokens=100000,
        supports_temperature=False,
    ),
    "gpt-5-mini": ModelCapability(
        max_tokens=32000,
    ),
    "gpt-5-nano": ModelCapability(
        max_tokens=16000,
    ),
    "gpt-4o": ModelCapability(
        max_tokens=16384,
    ),
    # Anthropic
    "claude-opus-4-1-20250805": ModelCapability(
        max_tokens=32000,
    ),
    "claude-opus-4-20250514": ModelCapability(
        max_tokens=32000,
    ),
    "claude-sonnet-4-20250514": ModelCapability(
        max_tokens=16000,
    ),
    "claude-3-haiku-20240307": ModelCapability(
        max_tokens=4096,
    ),
    # Ollama (local)
    "gpt-oss:20b": ModelCapability(
        max_tokens=8192,
    ),
    "gpt-oss:120b": ModelCapability(
        max_tokens=16000,
    ),
    "qwen3-coder:30b": ModelCapability(
        max_tokens=16000,
    ),
    "gemma3:27b": ModelCapability(
        max_tokens=8192,
        supports_tools=False,
    ),
    "magistral:latest": ModelCapability(
        max_tokens=16000,
    ),
    # Z.ai
    "glm-4.7": ModelCapability(
        temperature=1.0,
        max_tokens=131072,
        top_p=0.95,
    ),
    "glm-4.5-air": ModelCapability(
        temperature=1.0,
        max_tokens=16000,
        top_p=0.95,
    ),
    # Qwen Cloud
    "coder-model": ModelCapability(
        temperature=0.7,           # Official Qwen3-Coder recommendation (unchanged)
        max_tokens=65536,
        top_p=0.8,                 # Official Qwen3-Coder recommendation (unchanged)
        parallel_tool_calls=True,  # Enable concurrent file operations (empirically verified)
        extra_body={
            "top_k": 20,               # Official Qwen3-Coder recommendation
            "repetition_penalty": 1.05, # Official Qwen3-Coder recommendation
        },
    ),
}


def get_model_capabilities(model: str) -> ModelCapability:
    """Look up capabilities for a model. Falls back to DEFAULT_MODEL_CAPABILITY for unknown models."""
    caps = MODEL_CAPABILITIES.get(model)
    if caps is None:
        import logging
        logging.getLogger(__name__).warning(
            f"No capability entry for model '{model}' — using defaults "
            f"(max_tokens={DEFAULT_MODEL_CAPABILITY.max_tokens}, "
            f"supports_tools={DEFAULT_MODEL_CAPABILITY.supports_tools})"
        )
        return DEFAULT_MODEL_CAPABILITY
    return caps

# Tool Names
TOOL_READ_FILE = "read_file"
TOOL_LIST_DIRECTORY = "list_directory"
TOOL_WRITE_FILE = "write_file"
TOOL_GET_FILE_INFO = "get_file_info"
TOOL_EDIT_FILE = "edit_file"
TOOL_BASH = "bash"

# Available Tools List
AVAILABLE_TOOLS = [
    TOOL_READ_FILE,
    TOOL_LIST_DIRECTORY,
    TOOL_WRITE_FILE,
    TOOL_GET_FILE_INFO,
    TOOL_EDIT_FILE,
    TOOL_BASH,
]

# Demo Configuration
DEMO_PROMPTS = [
    ("List all files in the current directory", DEFAULT_MODEL),
    (
        "Create a file called demo.txt with the content 'Hello from Nano Agent!'",
        DEFAULT_MODEL,
    ),
    ("Read the file demo.txt and tell me what it says", DEFAULT_MODEL),
]

# System Prompts
NANO_AGENT_SYSTEM_PROMPT = """You are an autonomous coding agent that can read, write, edit files and execute shell commands.

## Tools Available
- read_file(file_path) — Read file contents
- write_file(file_path, content) — Create or overwrite a file
- edit_file(file_path, old_str, new_str) — Replace exact text in a file
- list_directory(directory_path) — List directory contents
- get_file_info(file_path) — Get file metadata
- bash(command) — Execute shell commands, scripts, and multi-command pipelines in the workspace

## Workflow
1. PLAN: Break the task into concrete steps
2. EXPLORE: Read existing files to understand the codebase before modifying
3. IMPLEMENT: Write or edit files, run commands as needed
4. VERIFY: Read back modified files or run tests to confirm correctness

## Rules
- Always read a file before editing it (to get exact text for old_str)
- Use bash for: installing dependencies, running tests, building projects, git operations, chained commands (&&, ;, |)
- Use edit_file for surgical changes to existing files (preferred over rewriting entire files)
- Use write_file for creating new files or when the entire content changes
- When a task involves multiple files, handle them one at a time
- If a command fails, read the error and adjust your approach
- Be concise in your final response — summarize what was done and any issues

If asked about general information, respond directly without using tools.
"""

# Error Messages
ERROR_NO_API_KEY = "{} environment variable is not set"
ERROR_PROVIDER_NOT_SUPPORTED = (
    "Provider '{}' not supported. Available providers: openai, anthropic, ollama, lmstudio, zai, qwen"
)
ERROR_FILE_NOT_FOUND = "Error: File not found: {}"
ERROR_NOT_A_FILE = "Error: Path is not a file: {}"
ERROR_DIR_NOT_FOUND = "Error: Directory not found: {}"
ERROR_NOT_A_DIR = "Error: Path is not a directory: {}"

# Success Messages
SUCCESS_FILE_WRITE = "Successfully wrote {} bytes to {}"
SUCCESS_FILE_EDIT = "updated"
SUCCESS_AGENT_COMPLETE = "Agent completed successfully in {:.2f}s"

# Version Info
VERSION = "1.0.0"
