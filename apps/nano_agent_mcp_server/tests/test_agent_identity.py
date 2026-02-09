"""
Tests for the agent_identity module.

Tests read_agent_instructions() and build_layered_prompt() functions
for the launch_agent MCP tool (US-010).
"""

import sys
import pytest
from pathlib import Path
from nano_agent.modules.agent_identity import read_agent_instructions, build_layered_prompt
from nano_agent.modules.constants import NANO_AGENT_SYSTEM_PROMPT


class TestReadAgentInstructions:
    """Tests for read_agent_instructions()."""

    def test_success(self, tmp_path):
        """Read AGENT.md successfully from a valid directory."""
        agent_dir = tmp_path / "my-agent"
        agent_dir.mkdir()
        agent_md = agent_dir / "AGENT.md"
        agent_md.write_text("You are a Python backend expert.\nFocus on FastAPI.", encoding="utf-8")

        result = read_agent_instructions(str(agent_dir))
        assert result == "You are a Python backend expert.\nFocus on FastAPI."

    def test_strips_whitespace(self, tmp_path):
        """Content should be stripped of leading/trailing whitespace."""
        agent_dir = tmp_path / "agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text("\n\n  You are an expert.  \n\n", encoding="utf-8")

        result = read_agent_instructions(str(agent_dir))
        assert result == "You are an expert."

    def test_path_not_found(self):
        """Raise ValueError when agent_path doesn't exist."""
        with pytest.raises(ValueError, match="Agent path does not exist"):
            read_agent_instructions("/nonexistent/path/that/does/not/exist")

    def test_path_is_file_not_dir(self, tmp_path):
        """Raise ValueError when agent_path is a file, not a directory."""
        some_file = tmp_path / "not-a-dir.txt"
        some_file.write_text("hello")

        with pytest.raises(ValueError, match="not a directory"):
            read_agent_instructions(str(some_file))

    def test_agent_md_not_found(self, tmp_path):
        """Raise ValueError when directory exists but AGENT.md is missing."""
        empty_dir = tmp_path / "empty-agent"
        empty_dir.mkdir()

        with pytest.raises(ValueError, match="AGENT.md not found"):
            read_agent_instructions(str(empty_dir))

    def test_empty_agent_md(self, tmp_path):
        """Raise ValueError when AGENT.md exists but is empty after stripping."""
        agent_dir = tmp_path / "empty-agent"
        agent_dir.mkdir()
        (agent_dir / "AGENT.md").write_text("   \n\n  \n  ", encoding="utf-8")

        with pytest.raises(ValueError, match="AGENT.md is empty"):
            read_agent_instructions(str(agent_dir))

    def test_unicode_content(self, tmp_path):
        """Handle Unicode content in AGENT.md correctly."""
        agent_dir = tmp_path / "unicode-agent"
        agent_dir.mkdir()
        content = "Handle: 中文, 日本語, 한국어, emoji 🚀"
        (agent_dir / "AGENT.md").write_text(content, encoding="utf-8")

        result = read_agent_instructions(str(agent_dir))
        assert result == content

    def test_relative_path(self, tmp_path, monkeypatch):
        """Resolve relative paths correctly."""
        agent_dir = tmp_path / "agents" / "backend"
        agent_dir.mkdir(parents=True)
        (agent_dir / "AGENT.md").write_text("Backend expert", encoding="utf-8")

        # Change CWD to parent so relative path works
        monkeypatch.chdir(tmp_path / "agents")

        result = read_agent_instructions("backend")
        assert result == "Backend expert"


class TestBuildLayeredPrompt:
    """Tests for build_layered_prompt()."""

    def test_base_and_agent_only(self):
        """With no workspace, prompt has Base + Agent layers only."""
        result = build_layered_prompt("You are an expert", "/tmp/agent", None)

        assert "## Base Instructions" in result
        assert NANO_AGENT_SYSTEM_PROMPT in result
        assert "## Agent Instructions" in result
        assert "You are an expert" in result
        assert "## Project Instructions" not in result

    def test_all_three_layers(self, tmp_path):
        """With workspace containing AGENT.md, prompt has all 3 layers."""
        workspace = tmp_path / "project"
        workspace.mkdir()
        (workspace / "AGENT.md").write_text("Use TypeScript strict mode.", encoding="utf-8")

        result = build_layered_prompt("You are a frontend expert", "/tmp/agent", str(workspace))

        assert "## Base Instructions" in result
        assert "## Agent Instructions" in result
        assert "You are a frontend expert" in result
        assert "## Project Instructions" in result
        assert "Use TypeScript strict mode." in result

    def test_layer_order(self, tmp_path):
        """Layers must appear in correct order: Base -> Agent -> Project."""
        workspace = tmp_path / "project"
        workspace.mkdir()
        (workspace / "AGENT.md").write_text("Project rules", encoding="utf-8")

        result = build_layered_prompt("Agent identity", "/tmp/agent", str(workspace))

        base_pos = result.index("## Base Instructions")
        agent_pos = result.index("## Agent Instructions")
        project_pos = result.index("## Project Instructions")

        assert base_pos < agent_pos < project_pos

    def test_workspace_no_agent_md(self, tmp_path):
        """When workspace exists but has no AGENT.md, skip Project layer."""
        workspace = tmp_path / "project-no-agent"
        workspace.mkdir()

        result = build_layered_prompt("Expert agent", "/tmp/agent", str(workspace))

        assert "## Base Instructions" in result
        assert "## Agent Instructions" in result
        assert "## Project Instructions" not in result

    def test_empty_workspace(self):
        """Empty string workspace treated same as None."""
        result = build_layered_prompt("Expert agent", "/tmp/agent", "")

        assert "## Base Instructions" in result
        assert "## Agent Instructions" in result
        assert "## Project Instructions" not in result

    def test_same_path_dedup(self, tmp_path):
        """When agent_path == workspace, skip Project layer (dedup)."""
        shared_dir = tmp_path / "shared"
        shared_dir.mkdir()
        (shared_dir / "AGENT.md").write_text("Shared instructions", encoding="utf-8")

        result = build_layered_prompt("Shared instructions", str(shared_dir), str(shared_dir))

        assert "## Agent Instructions" in result
        assert "## Project Instructions" not in result
        # AGENT.md content should appear only once under Agent Instructions
        assert result.count("Shared instructions") == 1

    def test_no_workspace_directory_appended(self):
        """build_layered_prompt does NOT append 'Workspace directory:' (caller's job)."""
        result = build_layered_prompt("Expert", "/tmp/agent", "/some/workspace")

        assert "Workspace directory:" not in result

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod doesn't restrict reads on Windows")
    def test_workspace_agent_md_read_error(self, tmp_path):
        """Graceful skip when workspace AGENT.md cannot be read."""
        workspace = tmp_path / "unreadable-project"
        workspace.mkdir()
        agent_md = workspace / "AGENT.md"
        agent_md.write_text("Rules", encoding="utf-8")
        # Make unreadable
        agent_md.chmod(0o000)

        try:
            result = build_layered_prompt("Expert", "/tmp/agent", str(workspace))
            # Should still succeed — graceful degradation
            assert "## Base Instructions" in result
            assert "## Agent Instructions" in result
            # May or may not have Project Instructions depending on OS
        finally:
            # Restore permissions for cleanup
            agent_md.chmod(0o644)

    def test_empty_workspace_agent_md(self, tmp_path):
        """Empty workspace AGENT.md (after stripping) should be skipped."""
        workspace = tmp_path / "empty-project"
        workspace.mkdir()
        (workspace / "AGENT.md").write_text("   \n\n  \n  ", encoding="utf-8")

        result = build_layered_prompt("Expert", "/tmp/agent", str(workspace))

        assert "## Project Instructions" not in result
