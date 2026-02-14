"""Tests for bash tool (renamed from run_command).

Covers:
- Phase 1: Constants rename (TOOL_BASH, AVAILABLE_TOOLS, system prompt)
- Phase 2: Function rename (bash in tool list, basic execution)
- Phase 3: Output cap 30K (no truncation, truncation, head/tail preservation)
- Phase 4: Persistent CWD (defaults, persistence, isolation, reset, parsing)
"""

import asyncio
import contextvars
import json
import tempfile
from pathlib import Path

import pytest


# ─── Helper to call the @function_tool-decorated bash function in tests ──────

async def _call_bash(command: str) -> str:
    """Invoke bash tool via FunctionTool.on_invoke_tool API."""
    from nano_agent.modules.nano_agent_tools import bash

    class _MinimalCtx:
        context = None

    return await bash.on_invoke_tool(_MinimalCtx(), json.dumps({"command": command}))


# ─── Phase 1: Constants Rename ───────────────────────────────────────────────


class TestBashConstants:
    """Phase 1: Verify constant rename and system prompt updates."""

    def test_bash_constant_exists(self):
        """TOOL_BASH constant should be 'bash', TOOL_RUN_COMMAND should not exist."""
        from nano_agent.modules.constants import TOOL_BASH
        assert TOOL_BASH == "bash"
        import nano_agent.modules.constants as c
        assert not hasattr(c, "TOOL_RUN_COMMAND"), "TOOL_RUN_COMMAND should be removed"

    def test_bash_in_available_tools(self):
        """AVAILABLE_TOOLS should contain 'bash', not 'run_command'."""
        from nano_agent.modules.constants import AVAILABLE_TOOLS
        assert "bash" in AVAILABLE_TOOLS
        assert "run_command" not in AVAILABLE_TOOLS

    def test_system_prompt_references_bash(self):
        """System prompt should reference bash(), not run_command()."""
        from nano_agent.modules.constants import NANO_AGENT_SYSTEM_PROMPT
        assert "bash(" in NANO_AGENT_SYSTEM_PROMPT
        assert "run_command(" not in NANO_AGENT_SYSTEM_PROMPT


# ─── Phase 2: Function Rename ────────────────────────────────────────────────


class TestBashFunction:
    """Phase 2: Verify function rename and basic execution."""

    def test_bash_in_tool_list(self):
        """get_nano_agent_tools() should include 'bash', not 'run_command'."""
        from nano_agent.modules.nano_agent_tools import get_nano_agent_tools
        tools = get_nano_agent_tools()
        tool_names = [getattr(t, "name", None) for t in tools]
        assert "bash" in tool_names, f"Expected 'bash' in {tool_names}"
        assert "run_command" not in tool_names, f"'run_command' should be removed"

    @pytest.mark.asyncio
    async def test_bash_executes_command(self):
        """bash('echo hello') should return output containing 'hello'."""
        from nano_agent.modules.nano_agent_tools import set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash("echo hello")
            assert "hello" in result
            assert "[exit_code: 0]" in result


# ─── Phase 3: Output Cap 30K ────────────────────────────────────────────────


class TestBashOutputCap:
    """Phase 3: Verify output cap increased from 8K to 30K."""

    def test_output_constants_exist(self):
        """BASH_OUTPUT_MAX_CHARS and ratio constants should exist."""
        from nano_agent.modules.nano_agent_tools import (
            BASH_OUTPUT_MAX_CHARS,
            BASH_OUTPUT_HEAD_RATIO,
            BASH_OUTPUT_TAIL_RATIO,
        )
        assert BASH_OUTPUT_MAX_CHARS == 30000
        assert 0 < BASH_OUTPUT_HEAD_RATIO < 1
        assert 0 < BASH_OUTPUT_TAIL_RATIO < 1
        assert BASH_OUTPUT_HEAD_RATIO + BASH_OUTPUT_TAIL_RATIO <= 1.0

    @pytest.mark.asyncio
    async def test_bash_no_truncation_under_limit(self):
        """Output under 30K chars should not be truncated."""
        from nano_agent.modules.nano_agent_tools import set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash("python3 -c \"print('x' * 29000)\"")
            assert "...(truncated)..." not in result
            assert "x" * 100 in result

    @pytest.mark.asyncio
    async def test_bash_truncation_at_limit(self):
        """Output over 30K chars should be truncated with marker."""
        from nano_agent.modules.nano_agent_tools import set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash("python3 -c \"print('A' * 35000)\"")
            assert "...(truncated)..." in result
            assert len(result) < 32000

    @pytest.mark.asyncio
    async def test_bash_truncation_preserves_head_and_tail(self):
        """Truncated output should preserve beginning and end of original."""
        from nano_agent.modules.nano_agent_tools import set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            cmd = "python3 -c \"print('HEAD_MARKER_' + 'x' * 35000 + '_TAIL_MARKER')\""
            result = await _call_bash(cmd)
            assert "HEAD_MARKER_" in result, "Head of output should be preserved"
            assert "_TAIL_MARKER" in result, "Tail of output should be preserved"


# ─── Phase 4: Persistent CWD ────────────────────────────────────────────────


class TestBashPersistentCWD:
    """Phase 4: Verify CWD persists between bash calls."""

    @pytest.mark.asyncio
    async def test_bash_cwd_defaults_to_workspace(self):
        """First bash call should use workspace as CWD."""
        from nano_agent.modules.nano_agent_tools import set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash("pwd")
            assert tmpdir in result

    @pytest.mark.asyncio
    async def test_bash_cwd_persists_after_cd(self):
        """After 'cd /tmp', next bash call should start in /tmp."""
        from nano_agent.modules.nano_agent_tools import set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            await _call_bash("cd /tmp")
            result = await _call_bash("pwd")
            assert "/tmp" in result, f"CWD should persist to /tmp, got: {result}"

    @pytest.mark.asyncio
    async def test_bash_cwd_persists_after_failed_cd(self):
        """After 'cd /nonexistent', CWD should remain unchanged."""
        from nano_agent.modules.nano_agent_tools import set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            await _call_bash("cd /nonexistent_dir_12345")
            result = await _call_bash("pwd")
            assert tmpdir in result, f"CWD should remain at workspace, got: {result}"

    @pytest.mark.asyncio
    async def test_bash_marker_stripped_from_output(self):
        """CWD marker should never appear in output returned to agent."""
        from nano_agent.modules.nano_agent_tools import set_workspace, _CWD_MARKER

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash("echo test")
            assert _CWD_MARKER not in result, "CWD marker should be stripped"

    @pytest.mark.asyncio
    async def test_bash_exit_code_preserved(self):
        """Exit code should reflect the user's command, not the CWD wrapper."""
        from nano_agent.modules.nano_agent_tools import set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = await _call_bash("false")
            assert "[exit_code: 1]" in result

    @pytest.mark.asyncio
    async def test_bash_cwd_isolation_between_tasks(self):
        """Concurrent tasks should have isolated CWD tracking."""
        from nano_agent.modules.nano_agent_tools import set_workspace

        results = {}

        async def task_a():
            set_workspace("/tmp")
            await _call_bash("cd /tmp")
            results["a"] = await _call_bash("pwd")

        async def task_b():
            with tempfile.TemporaryDirectory() as tmpdir:
                set_workspace(tmpdir)
                await _call_bash(f"cd {tmpdir}")
                results["b"] = await _call_bash("pwd")

        ctx_a = contextvars.copy_context()
        ctx_b = contextvars.copy_context()

        loop = asyncio.get_event_loop()
        fut_a = loop.run_in_executor(None, ctx_a.run, lambda: asyncio.run(task_a()))
        fut_b = loop.run_in_executor(None, ctx_b.run, lambda: asyncio.run(task_b()))
        await asyncio.gather(fut_a, fut_b)

        assert "/tmp" in results["a"], f"Task A should be in /tmp, got: {results['a']}"
        assert results["b"] != results["a"], "Tasks should have isolated CWDs"

    @pytest.mark.asyncio
    async def test_bash_cwd_resets_on_set_workspace(self):
        """set_workspace() should clear persistent CWD."""
        from nano_agent.modules.nano_agent_tools import set_workspace, get_bash_cwd

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            await _call_bash("cd /tmp")
            assert str(get_bash_cwd()) == "/tmp"

            with tempfile.TemporaryDirectory() as tmpdir2:
                set_workspace(tmpdir2)
                # Use resolve() to handle macOS /var → /private/var symlink
                assert get_bash_cwd().resolve() == Path(tmpdir2).resolve()


class TestParseCWD:
    """Phase 4: Unit tests for _parse_cwd_from_output helper."""

    def test_parse_cwd_no_marker(self):
        """No marker in output → returns (output, None)."""
        from nano_agent.modules.nano_agent_tools import _parse_cwd_from_output

        output, cwd = _parse_cwd_from_output("hello world\n")
        assert output == "hello world\n"
        assert cwd is None

    def test_parse_cwd_marker_in_user_output(self):
        """If marker appears twice, use LAST occurrence for CWD."""
        from nano_agent.modules.nano_agent_tools import _parse_cwd_from_output, _CWD_MARKER

        fake_output = f"some output\n{_CWD_MARKER}\n/fake/path\n{_CWD_MARKER}\n/real/cwd\n"
        output, cwd = _parse_cwd_from_output(fake_output)
        assert cwd == Path("/real/cwd"), f"Should use LAST marker, got: {cwd}"

    def test_parse_cwd_invalid_path(self):
        """Non-absolute path after marker → returns None."""
        from nano_agent.modules.nano_agent_tools import _parse_cwd_from_output, _CWD_MARKER

        fake_output = f"output\n{_CWD_MARKER}\nrelative/path\n"
        output, cwd = _parse_cwd_from_output(fake_output)
        assert cwd is None, "Relative path should not be accepted as CWD"


# ─── Process Group Isolation (Tier 1) ───────────────────────────────────────


class TestBashProcessGroups:
    """Tier 1: Verify process-group isolation prevents orphan processes."""

    def test_has_process_groups_flag(self):
        """_HAS_PROCESS_GROUPS should be True on macOS/Linux."""
        import sys
        from nano_agent.modules.nano_agent_tools import _HAS_PROCESS_GROUPS
        if sys.platform in ("linux", "darwin"):
            assert _HAS_PROCESS_GROUPS is True
        # On Windows, it should be False (not tested here)

    @pytest.mark.asyncio
    async def test_kill_process_tree_kills_group(self):
        """_kill_process_tree should kill entire process group."""
        import os
        import signal
        from nano_agent.modules.nano_agent_tools import _kill_process_tree, _HAS_PROCESS_GROUPS

        if not _HAS_PROCESS_GROUPS:
            pytest.skip("Process groups not available on this platform")

        # Start a subprocess that spawns a child
        proc = await asyncio.create_subprocess_shell(
            "sleep 60 & sleep 60",
            start_new_session=True,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.sleep(0.3)  # Let children spawn

        pgid = os.getpgid(proc.pid)
        _kill_process_tree(proc)
        await asyncio.sleep(0.3)  # Let signals propagate

        # Verify the entire group is dead
        with pytest.raises(ProcessLookupError):
            os.killpg(pgid, 0)

    @pytest.mark.asyncio
    async def test_kill_process_tree_handles_dead_process(self):
        """_kill_process_tree should not crash for already-dead process."""
        from nano_agent.modules.nano_agent_tools import _kill_process_tree

        proc = await asyncio.create_subprocess_shell(
            "true",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()  # Wait for it to finish

        # Should not raise
        _kill_process_tree(proc)

    @pytest.mark.asyncio
    async def test_bash_start_new_session(self):
        """bash subprocess should be in its own process group."""
        import os
        from nano_agent.modules.nano_agent_tools import set_workspace, _HAS_PROCESS_GROUPS

        if not _HAS_PROCESS_GROUPS:
            pytest.skip("Process groups not available on this platform")

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            # Run a command that outputs its own process group ID
            result = await _call_bash("python3 -c \"import os; print(os.getpgid(os.getpid()))\"")
            # The process group ID should differ from our own
            lines = result.strip().split('\n')
            pgid_line = lines[0].strip()
            if pgid_line.isdigit():
                child_pgid = int(pgid_line)
                our_pgid = os.getpgid(os.getpid())
                assert child_pgid != our_pgid, "Child should be in its own process group"
