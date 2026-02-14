"""Tests for security scan remediation fixes (A1, A2, A3)."""

import asyncio
import os
import signal
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

# A1: CORS tests
class TestCORSConfiguration:
    """Verify CORS is restricted to localhost origins."""

    def test_cors_not_wildcard(self):
        """CORS should NOT allow all origins."""
        from nano_agent.web.server import app
        cors_middleware = None
        for middleware in app.user_middleware:
            if middleware.cls.__name__ == "CORSMiddleware":
                cors_middleware = middleware
                break
        assert cors_middleware is not None, "CORSMiddleware not found"
        assert cors_middleware.kwargs.get("allow_origins") != ["*"], \
            "CORS should not use wildcard origin"

    def test_cors_allows_localhost(self):
        """CORS should allow localhost origins."""
        from nano_agent.web.server import app
        for middleware in app.user_middleware:
            if middleware.cls.__name__ == "CORSMiddleware":
                origins = middleware.kwargs.get("allow_origins", [])
                assert "http://localhost:8484" in origins
                assert "http://127.0.0.1:8484" in origins
                return
        pytest.fail("CORSMiddleware not found")


# A2: Workspace boundary tests
class TestWorkspaceBoundary:
    """Verify file tools enforce workspace focus boundary."""

    def setup_method(self):
        """Set up a temporary workspace."""
        import tempfile
        self.workspace = Path(tempfile.mkdtemp())
        # Create a test file inside workspace
        self.test_file = self.workspace / "test.txt"
        self.test_file.write_text("hello")

    def teardown_method(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.workspace, ignore_errors=True)

    def test_read_file_within_workspace(self):
        """read_file_raw should work for files within workspace."""
        from nano_agent.modules.nano_agent_tools import read_file_raw, set_workspace
        set_workspace(str(self.workspace))
        result = read_file_raw("test.txt")
        assert result == "hello"

    def test_read_file_outside_workspace(self):
        """read_file_raw should reject absolute paths outside workspace."""
        from nano_agent.modules.nano_agent_tools import read_file_raw, set_workspace
        set_workspace(str(self.workspace))
        result = read_file_raw("/etc/passwd")
        assert "Error" in result
        assert "workspace" in result.lower()

    def test_write_file_outside_workspace(self):
        """write_file_raw should reject paths outside workspace."""
        from nano_agent.modules.nano_agent_tools import write_file_raw, set_workspace
        set_workspace(str(self.workspace))
        result = write_file_raw("/tmp/should_not_exist_nano_test.txt", "bad")
        assert "Error" in result
        assert "workspace" in result.lower()
        assert not Path("/tmp/should_not_exist_nano_test.txt").exists()

    def test_edit_file_outside_workspace(self):
        """edit_file_raw should reject paths outside workspace."""
        from nano_agent.modules.nano_agent_tools import edit_file_raw, set_workspace
        set_workspace(str(self.workspace))
        result = edit_file_raw("/etc/hosts", "old", "new")
        assert "Error" in result
        assert "workspace" in result.lower()

    def test_relative_path_traversal_blocked(self):
        """Relative paths that escape workspace via .. should be blocked."""
        from nano_agent.modules.nano_agent_tools import read_file_raw, set_workspace
        set_workspace(str(self.workspace))
        result = read_file_raw("../../etc/passwd")
        assert "Error" in result
        assert "workspace" in result.lower()

    def test_write_file_within_workspace(self):
        """write_file_raw should work for paths within workspace."""
        from nano_agent.modules.nano_agent_tools import write_file_raw, set_workspace
        set_workspace(str(self.workspace))
        result = write_file_raw("output.txt", "written")
        assert "Error" not in result
        assert (self.workspace / "output.txt").read_text() == "written"


# A3: Background process cleanup tests
class TestCleanupResilience:
    """Verify background process cleanup handles cancellation."""

    def test_force_kill_remaining_exists(self):
        """_force_kill_remaining function should exist."""
        from nano_agent.modules.nano_agent_tools import _force_kill_remaining
        assert callable(_force_kill_remaining)

    def test_force_kill_remaining_handles_dead_pids(self):
        """_force_kill_remaining should not crash on already-dead PIDs."""
        from nano_agent.modules.nano_agent_tools import _force_kill_remaining, _bg_pids_var
        _bg_pids_var.set(None)
        pids = [99999]  # Non-existent PID
        _force_kill_remaining(pids)
        assert len(pids) == 0  # Should be cleared

    @pytest.mark.asyncio
    async def test_cleanup_catches_cancelled_error(self):
        """Cleanup should force-kill remaining if CancelledError occurs."""
        from nano_agent.modules.nano_agent_tools import (
            _cleanup_background_processes, _bg_pids_var
        )
        # Set up fake PIDs (non-existent, so kills will be no-ops)
        _bg_pids_var.set([99998, 99997])
        # Patch _kill_process_group_graceful to raise CancelledError on first call
        with patch(
            "nano_agent.modules.nano_agent_tools._kill_process_group_graceful",
            side_effect=asyncio.CancelledError()
        ), patch(
            "nano_agent.modules.nano_agent_tools._force_kill_remaining"
        ) as mock_force:
            await _cleanup_background_processes()
            mock_force.assert_called_once()
