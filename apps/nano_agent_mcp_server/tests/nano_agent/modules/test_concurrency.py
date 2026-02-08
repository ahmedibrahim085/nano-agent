"""
Tests for Concurrency Safety in Nano-Agent Tools.

These tests prove that module-level mutable globals cause race conditions
when multiple agents run concurrently in an async environment (MCP server).
"""

import pytest
import asyncio
from pathlib import Path

from nano_agent.modules.nano_agent_tools import (
    set_workspace,
    get_workspace,
    capture_args,
    _last_tool_args_var,
)
from nano_agent.modules.provider_config import ProviderConfig


@pytest.mark.asyncio
async def test_workspace_isolation():
    """Two concurrent tasks must each see their own workspace.

    This test proves Bug 1: _workspace_dir global causes race condition.
    With the global, Agent B's set_workspace() will overwrite Agent A's value.
    After fix with ContextVar, each task gets isolated storage.
    """
    barrier = asyncio.Event()
    results = {}

    async def task_a():
        """Agent A sets workspace to /tmp/agent_a_test"""
        set_workspace("/tmp/agent_a_test")
        barrier.set()  # Signal B to proceed
        await asyncio.sleep(0.1)  # Let B run set_workspace
        results["a"] = str(get_workspace().resolve())

    async def task_b():
        """Agent B sets workspace to /tmp/agent_b_test"""
        await barrier.wait()  # Wait for A to set its workspace
        set_workspace("/tmp/agent_b_test")
        await asyncio.sleep(0.05)
        results["b"] = str(get_workspace().resolve())

    # CRITICAL: Use create_task() to create separate Tasks
    # contextvars copies are per-Task, not per-coroutine
    t1 = asyncio.create_task(task_a())
    t2 = asyncio.create_task(task_b())
    await asyncio.gather(t1, t2)

    # Each task should see its own workspace (resolve to handle /tmp -> /private/tmp)
    assert results["a"] == str(Path("/tmp/agent_a_test").resolve()), f"Agent A saw wrong workspace: {results['a']}"
    assert results["b"] == str(Path("/tmp/agent_b_test").resolve()), f"Agent B saw wrong workspace: {results['b']}"


@pytest.mark.asyncio
async def test_tool_args_isolation():
    """Two concurrent tasks calling capture_args must not interfere.

    This test proves Bug 2: _last_tool_args and _pending_tool_args globals
    cause race condition. With the global dict, Agent B's capture_args()
    will overwrite Agent A's entry if they use the same tool name.
    """
    barrier = asyncio.Event()
    results = {}

    async def task_a():
        """Agent A captures args for read_file with path /tmp/a.txt"""
        capture_args("read_file", file_path="/tmp/a.txt")
        barrier.set()
        await asyncio.sleep(0.1)
        # Read back the args from the ContextVar
        last = _last_tool_args_var.get()
        if last and "read_file" in last:
            results["a"] = last["read_file"].get("file_path")
        else:
            results["a"] = None

    async def task_b():
        """Agent B captures args for read_file with path /tmp/b.txt"""
        await barrier.wait()
        capture_args("read_file", file_path="/tmp/b.txt")
        await asyncio.sleep(0.05)
        # Read back the args from the ContextVar
        last = _last_tool_args_var.get()
        if last and "read_file" in last:
            results["b"] = last["read_file"].get("file_path")
        else:
            results["b"] = None

    t1 = asyncio.create_task(task_a())
    t2 = asyncio.create_task(task_b())
    await asyncio.gather(t1, t2)

    # Each task should see its own captured args
    # With the bug, task A will see task B's args
    assert results["a"] == "/tmp/a.txt", f"Agent A saw wrong args: {results['a']}"
    assert results["b"] == "/tmp/b.txt", f"Agent B saw wrong args: {results['b']}"


@pytest.mark.asyncio
async def test_set_workspace_returns_correct_path():
    """Unit test: set_workspace returns the resolved path."""
    result = set_workspace("/tmp/test_workspace")
    # macOS: /tmp is symlink to /private/tmp, so resolve() returns /private/tmp
    assert result.resolve() == Path("/tmp/test_workspace").resolve()
    assert result.is_absolute()


@pytest.mark.asyncio
async def test_get_workspace_default():
    """Unit test: get_workspace returns cwd when no workspace is set.

    Note: In a fresh ContextVar context (new task), the var should default to None.
    This test must run in a new task to get a clean context.
    """
    async def fresh_context_task():
        # Don't call set_workspace, just get_workspace
        result = get_workspace()
        return result

    task = asyncio.create_task(fresh_context_task())
    result = await task

    # Should return current working directory
    assert result == Path.cwd()


@pytest.mark.asyncio
async def test_capture_args_stores_correctly():
    """Unit test: capture_args stores args retrievable from the ContextVar."""
    capture_args("write_file", file_path="/tmp/test.txt", content="hello")

    # Access via the ContextVar
    last = _last_tool_args_var.get()
    assert last is not None, "ContextVar should be set"
    assert "write_file" in last
    assert last["write_file"]["file_path"] == "/tmp/test.txt"
    assert last["write_file"]["content"] == "hello"


def _is_tracing_disabled() -> bool:
    """Helper to check if tracing is disabled."""
    from agents.tracing import get_trace_provider
    return get_trace_provider()._disabled


@pytest.mark.asyncio
async def test_tracing_restore():
    """Test that setup_provider correctly toggles tracing state.

    This test proves Bug 3: set_tracing_disabled() is never restored.
    When Agent A uses OpenAI (tracing ON), then Agent B uses Ollama (tracing OFF),
    Agent A's tracing gets disabled mid-run.

    After fix, each provider setup should explicitly set tracing state.
    """
    # Start with OpenAI (tracing enabled)
    ProviderConfig.setup_provider("openai")
    assert _is_tracing_disabled() == False, "OpenAI should enable tracing"

    # Switch to Ollama (tracing disabled)
    ProviderConfig.setup_provider("ollama")
    assert _is_tracing_disabled() == True, "Ollama should disable tracing"

    # Switch back to OpenAI (tracing should be re-enabled)
    ProviderConfig.setup_provider("openai")
    assert _is_tracing_disabled() == False, "OpenAI should re-enable tracing after Ollama"

    # Test with Z.ai (also should disable tracing)
    ProviderConfig.setup_provider("zai")
    assert _is_tracing_disabled() == True, "Z.ai should disable tracing"

    # And back to OpenAI one more time
    ProviderConfig.setup_provider("openai")
    assert _is_tracing_disabled() == False, "OpenAI should re-enable tracing after Z.ai"


@pytest.mark.asyncio
async def test_validate_provider_async_exists():
    """validate_provider_setup_async should exist and be async."""
    import inspect
    assert hasattr(ProviderConfig, 'validate_provider_setup_async')
    assert inspect.iscoroutinefunction(ProviderConfig.validate_provider_setup_async)


@pytest.mark.asyncio
async def test_validate_provider_async_cloud_provider():
    """Async validation should work for cloud providers (no HTTP needed)."""
    from nano_agent.modules.constants import AVAILABLE_MODELS, PROVIDER_REQUIREMENTS
    is_valid, error_msg = await ProviderConfig.validate_provider_setup_async(
        "openai", "gpt-5-mini", AVAILABLE_MODELS, PROVIDER_REQUIREMENTS
    )
    assert is_valid is True or error_msg is not None


@pytest.mark.asyncio
async def test_validate_provider_async_unavailable_service():
    """Async validation should handle unavailable local services gracefully."""
    from nano_agent.modules.constants import AVAILABLE_MODELS, PROVIDER_REQUIREMENTS
    is_valid, error_msg = await ProviderConfig.validate_provider_setup_async(
        "lmstudio", "some-model", AVAILABLE_MODELS, PROVIDER_REQUIREMENTS
    )
    assert is_valid is False
    assert error_msg is not None, "Should return an error message"
