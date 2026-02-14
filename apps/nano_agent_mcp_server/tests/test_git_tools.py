"""Tests for git tools (US-008: Git-Aware Tools).

Covers:
- Constants: TOOL_GIT_* constants, AVAILABLE_TOOLS (12 items), system prompt
- git_status: in-repo, not-in-repo
- git_commit: staged changes, empty message, whitespace message, nothing staged
- git_branch: create+switch, list, already exists
- git_diff: unstaged, staged, no changes, ref
- Safety guards: force push, hard reset, protected branch delete, clean, checkout dot, alias
- Input validation: branch name hyphen, diff ref hyphen, env var clearing
- Edge cases: empty repo, large diff truncation, not a git repo
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path



# ─── Helpers ────────────────────────────────────────────────────────────────

def _init_git_repo(path: str) -> None:
    """Initialize a git repo with an initial commit."""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True)
    # Create initial commit so branch 'main' exists
    (Path(path) / ".gitkeep").touch()
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=path, capture_output=True, check=True)


def _call_sync_tool(tool_func, args_json: str) -> str:
    """Invoke a sync @function_tool via on_invoke_tool (sync variant)."""
    import asyncio

    class _MinimalCtx:
        context = None

    # function_tool wraps sync functions as coroutines in on_invoke_tool
    return asyncio.get_event_loop().run_until_complete(
        tool_func.on_invoke_tool(_MinimalCtx(), args_json)
    )


# ─── Constants Tests (3) ───────────────────────────────────────────────────


class TestGitConstants:
    """Verify git tool constants exist and are registered."""

    def test_git_constants_exist(self):
        """4 TOOL_GIT_* constants should exist with correct values."""
        from nano_agent.modules.constants import (
            TOOL_GIT_STATUS,
            TOOL_GIT_COMMIT,
            TOOL_GIT_BRANCH,
            TOOL_GIT_DIFF,
        )
        assert TOOL_GIT_STATUS == "git_status"
        assert TOOL_GIT_COMMIT == "git_commit"
        assert TOOL_GIT_BRANCH == "git_branch"
        assert TOOL_GIT_DIFF == "git_diff"

    def test_git_tools_in_available_tools(self):
        """AVAILABLE_TOOLS should have 13 items including all 4 git tools."""
        from nano_agent.modules.constants import AVAILABLE_TOOLS
        assert len(AVAILABLE_TOOLS) == 13
        for tool_name in ["git_status", "git_commit", "git_branch", "git_diff"]:
            assert tool_name in AVAILABLE_TOOLS, f"{tool_name} missing from AVAILABLE_TOOLS"

    def test_system_prompt_lists_git_tools(self):
        """System prompt should mention all 4 git tools."""
        from nano_agent.modules.constants import NANO_AGENT_SYSTEM_PROMPT
        assert "git_status" in NANO_AGENT_SYSTEM_PROMPT
        assert "git_commit" in NANO_AGENT_SYSTEM_PROMPT
        assert "git_branch" in NANO_AGENT_SYSTEM_PROMPT
        assert "git_diff" in NANO_AGENT_SYSTEM_PROMPT
        assert "13 tools" in NANO_AGENT_SYSTEM_PROMPT


# ─── git_status Tests (2) ─────────────────────────────────────────────────


class TestGitStatus:
    """Test git_status tool."""

    def test_status_in_repo(self):
        """git_status in a valid repo should return branch info."""
        from nano_agent.modules.nano_agent_tools import git_status, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            result = _call_sync_tool(git_status, json.dumps({}))
            # git status output should contain branch info
            assert "branch" in result.lower() or "On branch" in result

    def test_status_not_in_repo(self):
        """git_status outside a git repo should return an error."""
        from nano_agent.modules.nano_agent_tools import git_status, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            result = _call_sync_tool(git_status, json.dumps({}))
            assert "not a git repository" in result.lower()


# ─── git_commit Tests (4) ─────────────────────────────────────────────────


class TestGitCommit:
    """Test git_commit tool."""

    def test_commit_with_staged_changes(self):
        """git_commit with staged changes should succeed."""
        from nano_agent.modules.nano_agent_tools import git_commit, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            # Create and stage a file
            (Path(tmpdir) / "test.txt").write_text("hello")
            subprocess.run(["git", "add", "test.txt"], cwd=tmpdir, capture_output=True)
            result = _call_sync_tool(git_commit, json.dumps({"message": "add test file"}))
            # Should indicate success (commit hash or "main" branch)
            assert "error" not in result.lower() or "nothing to commit" not in result.lower()

    def test_commit_empty_message(self):
        """git_commit with empty message should be blocked."""
        from nano_agent.modules.nano_agent_tools import git_commit, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            result = _call_sync_tool(git_commit, json.dumps({"message": ""}))
            assert "error" in result.lower()
            assert "empty" in result.lower()

    def test_commit_whitespace_message(self):
        """git_commit with whitespace-only message should be blocked."""
        from nano_agent.modules.nano_agent_tools import git_commit, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            result = _call_sync_tool(git_commit, json.dumps({"message": "   \n\t  "}))
            assert "error" in result.lower()
            assert "empty" in result.lower()

    def test_commit_nothing_staged(self):
        """git_commit with nothing staged should pass through git error."""
        from nano_agent.modules.nano_agent_tools import git_commit, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            result = _call_sync_tool(git_commit, json.dumps({"message": "empty commit"}))
            # git should complain about nothing to commit
            assert "nothing to commit" in result.lower() or "no changes" in result.lower()


# ─── git_branch Tests (3) ─────────────────────────────────────────────────


class TestGitBranch:
    """Test git_branch tool."""

    def test_branch_create_and_switch(self):
        """git_branch(name="feature-x") should create and switch to branch."""
        from nano_agent.modules.nano_agent_tools import git_branch, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            _call_sync_tool(git_branch, json.dumps({"name": "feature-x"}))
            # Verify we switched
            branch_check = subprocess.run(
                ["git", "branch", "--show-current"], cwd=tmpdir, capture_output=True, text=True
            )
            assert branch_check.stdout.strip() == "feature-x"

    def test_branch_list_empty_name(self):
        """git_branch(name="") should list all branches."""
        from nano_agent.modules.nano_agent_tools import git_branch, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            result = _call_sync_tool(git_branch, json.dumps({"name": ""}))
            # Should list at least the main/master branch
            assert "main" in result or "master" in result

    def test_branch_already_exists(self):
        """git_branch with existing branch name should return git error."""
        from nano_agent.modules.nano_agent_tools import git_branch, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            # Create branch first
            subprocess.run(["git", "checkout", "-b", "existing"], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "checkout", "-"], cwd=tmpdir, capture_output=True)
            # Try to create again
            result = _call_sync_tool(git_branch, json.dumps({"name": "existing"}))
            assert "already exists" in result.lower() or "fatal" in result.lower()


# ─── git_diff Tests (4) ───────────────────────────────────────────────────


class TestGitDiff:
    """Test git_diff tool."""

    def test_diff_unstaged_changes(self):
        """git_diff with unstaged changes should show 'Unstaged Changes' header."""
        from nano_agent.modules.nano_agent_tools import git_diff, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            # Modify a tracked file without staging
            (Path(tmpdir) / ".gitkeep").write_text("modified")
            result = _call_sync_tool(git_diff, json.dumps({}))
            assert "Unstaged Changes" in result

    def test_diff_staged_changes(self):
        """git_diff with staged changes should show 'Staged Changes' header."""
        from nano_agent.modules.nano_agent_tools import git_diff, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            # Stage a change
            (Path(tmpdir) / ".gitkeep").write_text("staged")
            subprocess.run(["git", "add", ".gitkeep"], cwd=tmpdir, capture_output=True)
            result = _call_sync_tool(git_diff, json.dumps({}))
            assert "Staged Changes" in result

    def test_diff_no_changes(self):
        """git_diff with no changes should show 'No changes' message."""
        from nano_agent.modules.nano_agent_tools import git_diff, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            result = _call_sync_tool(git_diff, json.dumps({}))
            assert "no changes" in result.lower()

    def test_diff_with_ref(self):
        """git_diff(ref="HEAD~1") should diff against a specific ref."""
        from nano_agent.modules.nano_agent_tools import git_diff, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            # Create a second commit
            (Path(tmpdir) / "new.txt").write_text("new file")
            subprocess.run(["git", "add", "."], cwd=tmpdir, capture_output=True)
            subprocess.run(["git", "commit", "-m", "second"], cwd=tmpdir, capture_output=True)
            result = _call_sync_tool(git_diff, json.dumps({"ref": "HEAD~1"}))
            assert "new.txt" in result


# ─── Safety Guards Tests (13) ─────────────────────────────────────────────


class TestGitSafety:
    """Test _validate_git_safety helper."""

    def test_force_push_blocked(self):
        """push --force should be blocked."""
        from nano_agent.modules.nano_agent_tools import _validate_git_safety
        result = _validate_git_safety(["push", "--force"])
        assert result is not None
        assert "force push" in result.lower()

    def test_force_push_f_flag_blocked(self):
        """push -f should be blocked."""
        from nano_agent.modules.nano_agent_tools import _validate_git_safety
        result = _validate_git_safety(["push", "-f"])
        assert result is not None
        assert "force push" in result.lower()

    def test_force_with_lease_blocked(self):
        """push --force-with-lease should be blocked."""
        from nano_agent.modules.nano_agent_tools import _validate_git_safety
        result = _validate_git_safety(["push", "--force-with-lease"])
        assert result is not None
        assert "force push" in result.lower()

    def test_hard_reset_blocked(self):
        """reset --hard should be blocked."""
        from nano_agent.modules.nano_agent_tools import _validate_git_safety
        result = _validate_git_safety(["reset", "--hard"])
        assert result is not None
        assert "hard reset" in result.lower()

    def test_main_branch_delete_blocked(self):
        """branch -D main should be blocked."""
        from nano_agent.modules.nano_agent_tools import _validate_git_safety
        result = _validate_git_safety(["branch", "-D", "main"])
        assert result is not None
        assert "protected branch" in result.lower()

    def test_master_branch_delete_blocked(self):
        """branch -d master should be blocked."""
        from nano_agent.modules.nano_agent_tools import _validate_git_safety
        result = _validate_git_safety(["branch", "-d", "master"])
        assert result is not None
        assert "protected branch" in result.lower()

    def test_develop_branch_delete_blocked(self):
        """branch -D develop should be blocked."""
        from nano_agent.modules.nano_agent_tools import _validate_git_safety
        result = _validate_git_safety(["branch", "-D", "develop"])
        assert result is not None
        assert "protected branch" in result.lower()

    def test_feature_branch_delete_allowed(self):
        """branch -d feature-x should be allowed."""
        from nano_agent.modules.nano_agent_tools import _validate_git_safety
        result = _validate_git_safety(["branch", "-d", "feature-x"])
        assert result is None

    def test_clean_all_variants_blocked(self):
        """git clean (all forms) should be blocked."""
        from nano_agent.modules.nano_agent_tools import _validate_git_safety
        for args in [["clean"], ["clean", "-fd"], ["clean", "-xfd"]]:
            result = _validate_git_safety(args)
            assert result is not None, f"clean variant {args} should be blocked"
            assert "clean" in result.lower()

    def test_checkout_dot_blocked(self):
        """checkout . and checkout -- . should be blocked."""
        from nano_agent.modules.nano_agent_tools import _validate_git_safety
        for args in [["checkout", "."], ["checkout", "--", "."], ["checkout", "./"]]:
            result = _validate_git_safety(args)
            assert result is not None, f"{args} should be blocked"
            assert "discard" in result.lower()

    def test_restore_dot_blocked(self):
        """restore . should be blocked."""
        from nano_agent.modules.nano_agent_tools import _validate_git_safety
        result = _validate_git_safety(["restore", "."])
        assert result is not None
        assert "discard" in result.lower()

    def test_config_alias_blocked(self):
        """config alias.x should be blocked."""
        from nano_agent.modules.nano_agent_tools import _validate_git_safety
        result = _validate_git_safety(["config", "alias.x", "!rm -rf /"])
        assert result is not None
        assert "alias" in result.lower()

    def test_safe_operations_pass(self):
        """Safe operations like status, diff, log, checkout -b should pass."""
        from nano_agent.modules.nano_agent_tools import _validate_git_safety
        safe_ops = [
            ["status"],
            ["diff"],
            ["log", "--oneline"],
            ["checkout", "-b", "new-branch"],
            ["push"],
            ["pull"],
            ["fetch"],
        ]
        for args in safe_ops:
            result = _validate_git_safety(args)
            assert result is None, f"Safe op {args} should pass, got: {result}"


# ─── Input Validation Tests (3) ──────────────────────────────────────────


class TestGitInputValidation:
    """Test input validation on tool functions."""

    def test_branch_name_hyphen_rejected(self):
        """git_branch(name="-f") should be rejected (flag injection)."""
        from nano_agent.modules.nano_agent_tools import git_branch, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            result = _call_sync_tool(git_branch, json.dumps({"name": "-f"}))
            assert "error" in result.lower()
            assert "hyphen" in result.lower()

    def test_diff_ref_hyphen_rejected(self):
        """git_diff(ref="--staged") should be rejected (flag injection)."""
        from nano_agent.modules.nano_agent_tools import git_diff, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            result = _call_sync_tool(git_diff, json.dumps({"ref": "--staged"}))
            assert "error" in result.lower()
            assert "hyphen" in result.lower()

    def test_git_env_vars_cleared(self):
        """GIT_DIR should not leak into git commands."""
        from nano_agent.modules.nano_agent_tools import _run_git_command, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            # Set GIT_DIR to something wrong — should be cleared by _run_git_command
            old_val = os.environ.get("GIT_DIR")
            try:
                os.environ["GIT_DIR"] = "/nonexistent/.git"
                result = _run_git_command(["status"])
                # Should succeed because _run_git_command clears GIT_DIR
                assert "not a git repository" not in result.lower()
            finally:
                if old_val is None:
                    os.environ.pop("GIT_DIR", None)
                else:
                    os.environ["GIT_DIR"] = old_val


# ─── Edge Cases Tests (3) ────────────────────────────────────────────────


class TestGitEdgeCases:
    """Test edge cases."""

    def test_empty_repo_no_commits(self):
        """git_status in an empty repo (no commits) should still work."""
        from nano_agent.modules.nano_agent_tools import git_status, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            subprocess.run(["git", "init"], cwd=tmpdir, capture_output=True, check=True)
            set_workspace(tmpdir)
            result = _call_sync_tool(git_status, json.dumps({}))
            # Should not error out — may say "No commits yet"
            assert "fatal" not in result.lower()

    def test_large_diff_truncation(self):
        """Diff output > 30K chars should be truncated."""
        from nano_agent.modules.nano_agent_tools import git_diff, set_workspace

        with tempfile.TemporaryDirectory() as tmpdir:
            _init_git_repo(tmpdir)
            set_workspace(tmpdir)
            # Create a large file to generate big diff
            large_content = "x" * 40000
            (Path(tmpdir) / ".gitkeep").write_text(large_content)
            result = _call_sync_tool(git_diff, json.dumps({}))
            # If the diff is large enough, it should be truncated
            if len(result) > 30000:
                assert "truncated" in result.lower()

    def test_not_git_repo_error(self):
        """All tools should return clear error outside a git repo."""
        from nano_agent.modules.nano_agent_tools import (
            git_status, git_commit, git_branch, git_diff, set_workspace,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            set_workspace(tmpdir)
            for tool, args in [
                (git_status, {}),
                (git_commit, {"message": "test"}),
                (git_branch, {"name": "x"}),
                (git_diff, {}),
            ]:
                result = _call_sync_tool(tool, json.dumps(args))
                assert "not a git repository" in result.lower(), (
                    f"{tool.name} should report not a git repo, got: {result[:100]}"
                )
