import json
import re
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent.parent / ".claude" / "settings.json"

def test_settings_file_exists():
    """Settings file must exist."""
    assert SETTINGS_PATH.exists(), f"Settings file not found at {SETTINGS_PATH}"

def test_no_absolute_home_paths():
    """No hook command should contain absolute paths to a user's home directory."""
    content = SETTINGS_PATH.read_text()
    # Match any /Users/xxx/ or /home/xxx/ pattern
    matches = re.findall(r'/(?:Users|home)/\w+/', content)
    assert len(matches) == 0, f"Found personal absolute paths: {matches}"

def test_no_hardcoded_project_paths():
    """No hook command should contain hardcoded project directory paths."""
    content = SETTINGS_PATH.read_text()
    # Should not contain any path that looks like /absolute/path/to/project/.claude/hooks/
    matches = re.findall(r'"command":\s*"[^"]*?/[^"]*?/\.claude/hooks/', content)
    # Filter: allow lines that use $CLAUDE_PROJECT_DIR
    hardcoded = [m for m in matches if '$CLAUDE_PROJECT_DIR' not in m]
    assert len(hardcoded) == 0, f"Found hardcoded project paths in commands: {hardcoded}"

def test_all_hooks_use_claude_project_dir():
    """Every hook command referencing .claude/hooks/ must use $CLAUDE_PROJECT_DIR."""
    with open(SETTINGS_PATH) as f:
        data = json.load(f)

    hooks = data.get("hooks", {})
    for event_type, hook_list in hooks.items():
        for entry in hook_list:
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                if ".claude/hooks/" in cmd:
                    assert '$CLAUDE_PROJECT_DIR' in cmd, (
                        f"Hook '{event_type}' command does not use $CLAUDE_PROJECT_DIR: {cmd}"
                    )

def test_hook_command_format():
    """Each hook command should follow the portable format exactly."""
    with open(SETTINGS_PATH) as f:
        data = json.load(f)

    hooks = data.get("hooks", {})
    for event_type, hook_list in hooks.items():
        for entry in hook_list:
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                if ".claude/hooks/" in cmd:
                    # Must start with: uv run "$CLAUDE_PROJECT_DIR"/.claude/hooks/
                    assert cmd.startswith('uv run "$CLAUDE_PROJECT_DIR"/.claude/hooks/'), (
                        f"Hook '{event_type}' has wrong format. Expected: "
                        f'uv run "$CLAUDE_PROJECT_DIR"/.claude/hooks/... '
                        f"Got: {cmd}"
                    )

def test_settings_json_is_valid():
    """Settings file must be valid JSON after modifications."""
    with open(SETTINGS_PATH) as f:
        data = json.load(f)
    assert "hooks" in data, "Missing 'hooks' key in settings"
    # Verify all 8 hook types exist
    expected_types = ["PreToolUse", "PostToolUse", "Notification", "Stop",
                      "SubagentStop", "PreCompact", "UserPromptSubmit", "SessionStart"]
    for hook_type in expected_types:
        assert hook_type in data["hooks"], f"Missing hook type: {hook_type}"

def test_stop_hook_preserves_continue_on_error():
    """Stop hook must keep continueOnError: true."""
    with open(SETTINGS_PATH) as f:
        data = json.load(f)
    stop_hooks = data["hooks"]["Stop"]
    stop_hook = stop_hooks[0]["hooks"][0]
    assert stop_hook.get("continueOnError") is True, "Stop hook must have continueOnError: true"

def test_hook_args_preserved():
    """Hook commands with extra args (--chat, --log-only) must preserve them."""
    with open(SETTINGS_PATH) as f:
        data = json.load(f)

    # Stop hook should have --chat
    stop_cmd = data["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert "--chat" in stop_cmd, f"Stop hook missing --chat arg: {stop_cmd}"

    # UserPromptSubmit should have --log-only
    ups_cmd = data["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    assert "--log-only" in ups_cmd, f"UserPromptSubmit hook missing --log-only arg: {ups_cmd}"
