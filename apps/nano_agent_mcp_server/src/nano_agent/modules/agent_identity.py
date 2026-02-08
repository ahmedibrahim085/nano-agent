"""
Agent identity loader for launch_agent MCP tool.

Reads AGENT.md files from agent directories and builds layered system prompts
that combine agent identity with optional project-specific instructions.
"""

import logging
from pathlib import Path

from .constants import NANO_AGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def read_agent_instructions(agent_path: str) -> str:
    """Read agent identity instructions from agent_path/AGENT.md.

    Args:
        agent_path: Path to directory containing AGENT.md

    Returns:
        Content of AGENT.md as a string (stripped of leading/trailing whitespace)

    Raises:
        ValueError: If agent_path doesn't exist or AGENT.md not found
    """
    path = Path(agent_path).resolve()
    if not path.exists():
        raise ValueError(f"Agent path does not exist: {agent_path}")
    if not path.is_dir():
        raise ValueError(f"Agent path is not a directory: {agent_path}")
    agent_file = path / "AGENT.md"
    if not agent_file.exists():
        raise ValueError(f"AGENT.md not found in: {agent_path}")
    try:
        content = agent_file.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Failed to read AGENT.md: {e}")
    logger.debug(f"Read agent instructions from {agent_file} ({len(content)} chars)")
    return content.strip()


def build_layered_prompt(agent_instructions: str, agent_path: str, workspace: str | None) -> str:
    """Build a layered system prompt with agent identity and optional project rules.

    Layers (in order):
    1. Base Instructions — NANO_AGENT_SYSTEM_PROMPT (always)
    2. Agent Instructions — from agent_path/AGENT.md (always, passed as parameter)
    3. Project Instructions — from workspace/AGENT.md (only if exists AND workspace != agent_path)

    NOTE: Does NOT append "Workspace directory:" — the caller handles that.

    Args:
        agent_instructions: Content from agent_path/AGENT.md (already loaded)
        agent_path: Path to agent directory (for dedup check)
        workspace: Path to workspace directory (optional)

    Returns:
        Assembled system prompt string
    """
    sections = [f"## Base Instructions\n{NANO_AGENT_SYSTEM_PROMPT}"]
    sections.append(f"## Agent Instructions\n{agent_instructions}")
    
    if workspace is not None and workspace != "":
        resolved_agent = str(Path(agent_path).resolve())
        resolved_workspace = str(Path(workspace).resolve())
        if resolved_agent != resolved_workspace:
            workspace_agent_file = Path(workspace) / "AGENT.md"
            if workspace_agent_file.exists():
                try:
                    content = workspace_agent_file.read_text(encoding="utf-8")
                    stripped_content = content.strip()
                    if stripped_content:
                        sections.append(f"## Project Instructions\n{stripped_content}")
                        logger.info(f"Loaded project instructions from {workspace_agent_file}")
                except OSError as e:
                    logger.warning(f"Failed to read workspace AGENT.md: {e}")
    
    return "\n\n".join(sections)
