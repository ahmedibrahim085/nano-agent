"""Tests for bash_background tool (Tier 3).

Covers:
- Constants (TOOL_BASH_BACKGROUND, AVAILABLE_TOOLS, system prompt)
- Basic execution (start, PID, output file, stdout capture)
- Process management (tracking, limit, pruning, cleanup)
- ContextVar isolation
- Error handling
- Edge cases
- Tool registration
"""

import asyncio
import contextvars
import json
import os
import signal
import sys
import tempfile
import time
from pathlib import Path

import pytest


# ─── Helper to call @function_tool-decorated functions in tests ──────────────

async def _call_bash_background(command: str) -> str:
    """Invoke bash_background tool via FunctionTool.on_invoke_tool API."""
    from nano_agent.modules.nano_agent_tools import bash_background

    class _MinimalCtx:
        context = None

    return await bash_background.on_invoke_tool(
        _MinimalCtx(), json.dumps({"command": command})
    )


async def _call_bash(command: str) -> str:
    """Invoke bash tool via FunctionTool.on_invoke_tool API."""
    from nano_agent.modules.nano_agent_tools import bash

    class _MinimalCtx:
        context = None

    return await bash.on_invoke_tool(_MinimalCtx(), json.dumps({"command": command}))


def _extract_pid(result: str) -> int:
    """Extract PID from bash_background result string."""
    for line in result.split('\n'):
        if line.startswith("PID:"):
            return int(line.split(":")[1].strip())
    raise ValueError(f"No PID found in: {result}")


def _extract_output_path(result: str) -> str:
    """Extract output file path from bash_background result string."""
    for line in result.split('\n'):
        if line.startswith("Output file:"):
            return line.split(":", 1)[1].strip()
    raise ValueError(f"No output file found in: {result}")


# ─── Constants ───────────────────────────────────────────────────────────────


class TestBashBackgroundConstants:
    """Verify bash_background constant and system prompt updates."""

    def test_bash_background_constant_exists(self):
        from nano_agent.modules.constants import TOOL_BASH_BACKGROUND
        assert TOOL_BASH_BACKGROUND == "bash_background"

    def test_bash_background_in_available_tools(self):
        from nano_agent.modules.constants import AVAILABLE_TOOLS
        assert len(AVAILABLE_TOOLS) == 13
        assert "bash_background" in AVAILABLE_TOOLS

    def test_system_prompt_mentions_bash_background(self):
        from nano_agent.modules.constants import NANO_AGENT_SYSTEM_PROMPT
        assert "bash_background(" in NANO_AGENT_SYSTEM_PROMPT
        assert "13 tools" in NANO_AGENT_SYSTEM_PROMPT


# ─── Basic Execution ─────────────────────────────────────────────────────────


class TestBashBackgroundExecution:
    """Verify basic bash_background execution."""

    @pytest.mark.asyncio
    async def test_background_starts_and_returns_pid(self):
        from nano_agent.modules.nano_agent_tools import set_workspace
        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash_background("sleep 30")
            assert "PID:" in result
            pid = _extract_pid(result)
            assert pid > 0
            # Cleanup
            os.kill(pid, signal.SIGKILL)

    @pytest.mark.asyncio
    async def test_background_pid_is_alive(self):
        from nano_agent.modules.nano_agent_tools import set_workspace
        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash_background("sleep 30")
            pid = _extract_pid(result)
            try:
                os.kill(pid, 0)  # Should not raise — process is alive
            finally:
                os.kill(pid, signal.SIGKILL)

    @pytest.mark.asyncio
    async def test_background_output_file_created(self):
        from nano_agent.modules.nano_agent_tools import set_workspace
        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash_background("sleep 30")
            output_path = _extract_output_path(result)
            assert Path(output_path).exists()
            pid = _extract_pid(result)
            os.kill(pid, signal.SIGKILL)

    @pytest.mark.asyncio
    async def test_background_output_captures_stdout(self):
        from nano_agent.modules.nano_agent_tools import set_workspace
        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash_background("echo hello_from_background")
            output_path = _extract_output_path(result)
            await asyncio.sleep(0.5)  # Let output flush
            content = Path(output_path).read_text()
            assert "hello_from_background" in content


# ─── Process Management ──────────────────────────────────────────────────────


class TestBashBackgroundProcessManagement:
    """Verify process tracking, limits, pruning, and cleanup."""

    @pytest.mark.asyncio
    async def test_background_pid_tracked(self):
        from nano_agent.modules.nano_agent_tools import set_workspace, _get_bg_pids
        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash_background("sleep 30")
            pid = _extract_pid(result)
            assert pid in _get_bg_pids()
            os.kill(pid, signal.SIGKILL)

    @pytest.mark.asyncio
    async def test_background_max_limit_enforced(self):
        from nano_agent.modules.nano_agent_tools import (
            set_workspace, MAX_BACKGROUND_PROCESSES, _cleanup_background_processes,
        )
        pids = []
        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            try:
                for _ in range(MAX_BACKGROUND_PROCESSES):
                    res = await _call_bash_background("sleep 60")
                    pids.append(_extract_pid(res))

                # The next one should fail
                result = await _call_bash_background("sleep 60")
                assert "Maximum" in result
            finally:
                await _cleanup_background_processes()

    @pytest.mark.asyncio
    async def test_background_dead_procs_pruned_from_limit(self):
        from nano_agent.modules.nano_agent_tools import (
            set_workspace, MAX_BACKGROUND_PROCESSES, _cleanup_background_processes,
        )
        pids = []
        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            try:
                # Fill up to limit
                for _ in range(MAX_BACKGROUND_PROCESSES):
                    res = await _call_bash_background("sleep 60")
                    pids.append(_extract_pid(res))

                # Kill 3 of them
                for pid in pids[:3]:
                    os.kill(pid, signal.SIGKILL)
                await asyncio.sleep(0.3)

                # Should succeed because dead procs are pruned
                result = await _call_bash_background("sleep 60")
                assert "PID:" in result
                pids.append(_extract_pid(result))
            finally:
                await _cleanup_background_processes()

    @pytest.mark.asyncio
    async def test_background_cleanup_kills_all(self):
        from nano_agent.modules.nano_agent_tools import (
            set_workspace, _cleanup_background_processes, _get_bg_pids,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            res1 = await _call_bash_background("sleep 60")
            res2 = await _call_bash_background("sleep 60")
            pid1 = _extract_pid(res1)
            pid2 = _extract_pid(res2)

            await _cleanup_background_processes()
            await asyncio.sleep(0.3)

            # Both should be dead
            for pid in (pid1, pid2):
                with pytest.raises(ProcessLookupError):
                    os.kill(pid, 0)

            # PID list should be empty
            assert _get_bg_pids() == []


# ─── ContextVar Isolation ────────────────────────────────────────────────────


class TestBashBackgroundContextIsolation:
    """Verify per-context PID list isolation."""

    @pytest.mark.asyncio
    async def test_background_pids_per_context(self):
        from nano_agent.modules.nano_agent_tools import set_workspace, _get_bg_pids, _bg_pids_var

        results = {}

        def run_in_ctx(name, tmpdir):
            async def inner():
                set_workspace(tmpdir)
                _bg_pids_var.set(None)  # Reset for this context
                pids = _get_bg_pids()
                pids.append(999 if name == "a" else 888)
                results[name] = list(pids)
            asyncio.run(inner())

        with tempfile.TemporaryDirectory() as tmpdir_a, \
             tempfile.TemporaryDirectory() as tmpdir_b:
            ctx_a = contextvars.copy_context()
            ctx_b = contextvars.copy_context()
            ctx_a.run(run_in_ctx, "a", tmpdir_a)
            ctx_b.run(run_in_ctx, "b", tmpdir_b)

        assert results["a"] == [999]
        assert results["b"] == [888]

    @pytest.mark.asyncio
    async def test_set_workspace_resets_bg_pids(self):
        from nano_agent.modules.nano_agent_tools import set_workspace, _get_bg_pids

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            pids = _get_bg_pids()
            pids.append(12345)  # Simulate a tracked PID

            set_workspace(tmpdir)  # Reset
            assert _get_bg_pids() == []

    @pytest.mark.asyncio
    async def test_set_workspace_kills_leftover_pids(self):
        from nano_agent.modules.nano_agent_tools import set_workspace, _get_bg_pids

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash_background("sleep 60")
            pid = _extract_pid(result)

            # Don't call cleanup — simulate crash recovery
            set_workspace(tmpdir)  # Should kill leftover
            await asyncio.sleep(0.3)

            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)


# ─── Error Handling ──────────────────────────────────────────────────────────


class TestBashBackgroundErrors:
    """Verify error handling."""

    @pytest.mark.asyncio
    async def test_background_invalid_workspace(self):
        from nano_agent.modules.nano_agent_tools import _bash_cwd_var
        _bash_cwd_var.set(Path("/nonexistent_dir_abc123"))
        result = await _call_bash_background("sleep 1")
        assert "Workspace directory does not exist" in result

    @pytest.mark.asyncio
    async def test_background_cleanup_handles_dead_process(self):
        from nano_agent.modules.nano_agent_tools import (
            set_workspace, _get_bg_pids, _cleanup_background_processes,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash_background("sleep 60")
            pid = _extract_pid(result)

            # Kill it manually
            os.kill(pid, signal.SIGKILL)
            await asyncio.sleep(0.3)

            # Cleanup should not crash
            await _cleanup_background_processes()

    @pytest.mark.asyncio
    async def test_background_output_file_cleaned_on_start_error(self):
        from unittest.mock import patch
        from nano_agent.modules.nano_agent_tools import set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)

            with patch("asyncio.create_subprocess_shell", side_effect=OSError("mock error")):
                result = await _call_bash_background("sleep 1")
                assert "Error starting background process" in result

            # Verify no leftover output files
            log_files = list(Path(tmpdir).glob("nano_bg_*"))
            assert len(log_files) == 0, f"Leftover output files: {log_files}"


# ─── Edge Cases ──────────────────────────────────────────────────────────────


class TestBashBackgroundEdgeCases:
    """Verify edge case behavior."""

    @pytest.mark.asyncio
    async def test_background_short_lived_process(self):
        from nano_agent.modules.nano_agent_tools import set_workspace, _get_bg_pids
        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash_background("echo done")
            pid = _extract_pid(result)
            assert pid in _get_bg_pids()
            output_path = _extract_output_path(result)
            await asyncio.sleep(0.5)
            content = Path(output_path).read_text()
            assert "done" in content

    @pytest.mark.asyncio
    async def test_background_uses_workspace_cwd(self):
        from nano_agent.modules.nano_agent_tools import set_workspace
        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash_background("pwd > cwd_check.txt")
            await asyncio.sleep(0.5)
            cwd_file = Path(tmpdir) / "cwd_check.txt"
            assert cwd_file.exists()
            cwd_content = cwd_file.read_text().strip()
            assert Path(cwd_content).resolve() == Path(tmpdir).resolve()

    @pytest.mark.asyncio
    async def test_background_uses_process_groups(self):
        from nano_agent.modules.nano_agent_tools import set_workspace, _HAS_PROCESS_GROUPS
        if not _HAS_PROCESS_GROUPS:
            pytest.skip("Process groups not available")
        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash_background(
                "python3 -c \"import os; open('sid.txt','w').write(str(os.getsid(os.getpid())))\""
            )
            pid = _extract_pid(result)
            await asyncio.sleep(0.5)
            sid_file = Path(tmpdir) / "sid.txt"
            if sid_file.exists():
                child_sid = int(sid_file.read_text().strip())
                our_sid = os.getsid(os.getpid())
                assert child_sid != our_sid, "Child should be in its own session"
            os.kill(pid, signal.SIGKILL)


# ─── Tool Registration ──────────────────────────────────────────────────────


class TestBashBackgroundToolRegistration:
    """Verify bash_background in tool list."""

    def test_bash_background_in_tool_list(self):
        from nano_agent.modules.nano_agent_tools import get_nano_agent_tools
        tools = get_nano_agent_tools()
        tool_names = [getattr(t, "name", None) for t in tools]
        assert len(tools) == 13, f"Expected 13 tools, got {len(tools)}: {tool_names}"
        assert "bash_background" in tool_names
