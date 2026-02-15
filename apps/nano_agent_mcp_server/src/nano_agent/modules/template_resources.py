"""Template resources module for nano-agent MCP server.

Provides access to agent, skill, and guide templates as MCP resources.
"""

import logging
from collections.abc import Callable
from importlib.resources import files
from typing import Any

logger = logging.getLogger(__name__)

# Resource URI prefix for nano-agent templates
RESOURCE_URI_PREFIX = "nano-agent://templates/"

# Valid template categories
VALID_CATEGORIES = ("agents", "skills", "agent-identities", "guides")

# Template registry - all available templates
TEMPLATE_REGISTRY = [
    {
        "category": "agents",
        "name": "README.md",
        "description": "Overview of Claude Code agent templates for nano-agent dispatch",
        "mime_type": "text/markdown",
    },
    {
        "category": "agents",
        "name": "nano-reviewer.md",
        "description": "Code reviewer agent that dispatches to external LLMs",
        "mime_type": "text/markdown",
    },
    {
        "category": "agents",
        "name": "nano-researcher.md",
        "description": "Codebase researcher agent with external LLM analysis",
        "mime_type": "text/markdown",
    },
    {
        "category": "agents",
        "name": "nano-implementer.md",
        "description": "Code implementer agent that dispatches coding work to external LLMs",
        "mime_type": "text/markdown",
    },
    {
        "category": "agents",
        "name": "nano-teammate.md",
        "description": "Peer teammate agent for multi-agent collaboration",
        "mime_type": "text/markdown",
    },
    {
        "category": "skills",
        "name": "README.md",
        "description": "Overview of skill templates for nano-agent dispatch",
        "mime_type": "text/markdown",
    },
    {
        "category": "skills",
        "name": "nano-dispatch/SKILL.md",
        "description": "Quick dispatch skill for one-off nano-agent tasks",
        "mime_type": "text/markdown",
    },
    {
        "category": "agent-identities",
        "name": "README.md",
        "description": "Overview of AGENT.md identity templates for launch_agent",
        "mime_type": "text/markdown",
    },
    {
        "category": "agent-identities",
        "name": "general-coder/AGENT.md",
        "description": "General-purpose coding agent identity",
        "mime_type": "text/markdown",
    },
    {
        "category": "agent-identities",
        "name": "code-reviewer/AGENT.md",
        "description": "Code review specialist identity",
        "mime_type": "text/markdown",
    },
    {
        "category": "agent-identities",
        "name": "tdd-engineer/AGENT.md",
        "description": "TDD practitioner identity with RED-GREEN-REFACTOR discipline",
        "mime_type": "text/markdown",
    },
    {
        "category": "agent-identities",
        "name": "backend-expert/AGENT.md",
        "description": "Backend development expert identity",
        "mime_type": "text/markdown",
    },
    {
        "category": "guides",
        "name": "when-to-use-what.md",
        "description": "Decision guide for choosing between nano-agent execution mechanisms",
        "mime_type": "text/markdown",
    },
    {
        "category": "guides",
        "name": "installation.md",
        "description": "Reference card: where each template file type goes",
        "mime_type": "text/markdown",
    },
    {
        "category": "guides",
        "name": "multi-instance.md",
        "description": "Reference card: running multiple agents without naming collisions",
        "mime_type": "text/markdown",
    },
    {
        "category": "guides",
        "name": "team-patterns.md",
        "description": "Reference card: ready-to-use team compositions",
        "mime_type": "text/markdown",
    },
    {
        "category": "guides",
        "name": "recipes/README.md",
        "description": "Index of step-by-step recipes for nano-agent workflows",
        "mime_type": "text/markdown",
    },
    {
        "category": "guides",
        "name": "recipes/01-mcp-direct-dispatch.md",
        "description": "Recipe: dispatch a self-contained task to a specific model",
        "mime_type": "text/markdown",
    },
    {
        "category": "guides",
        "name": "recipes/02-teammate-collaboration.md",
        "description": "Recipe: multi-agent team collaboration with nano-agent",
        "mime_type": "text/markdown",
    },
    {
        "category": "guides",
        "name": "recipes/03-background-bash.md",
        "description": "Recipe: run long-running commands in the background",
        "mime_type": "text/markdown",
    },
    {
        "category": "guides",
        "name": "recipes/04-launch-agent-identity.md",
        "description": "Recipe: use launch_agent with persistent AGENT.md identity",
        "mime_type": "text/markdown",
    },
    {
        "category": "guides",
        "name": "recipes/05-skill-quick-dispatch.md",
        "description": "Recipe: quick dispatch via /nano-dispatch skill",
        "mime_type": "text/markdown",
    },
    {
        "category": "",
        "name": "README.md",
        "description": "Overview of all nano-agent template categories",
        "mime_type": "text/markdown",
    },
]


def load_template(category: str, name: str) -> str:
    """Load a template file from the templates directory.

    Args:
        category: Template category (agents, skills, agent-identities, guides, or empty string for top-level)
        name: Template file name (may include subdirectories like "recipes/01-mcp-direct-dispatch.md")

    Returns:
        Template content as string

    Raises:
        ValueError: If path traversal is detected or category is invalid
        FileNotFoundError: If template file does not exist
    """
    # Block path traversal
    if ".." in name:
        raise ValueError("Path traversal not allowed")

    # Validate category (allow empty string for top-level README.md)
    if category and category not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category '{category}'. Valid categories: {VALID_CATEGORIES}"
        )

    # Build resource path
    base = files("nano_agent") / "templates"

    # Add category subdirectory if specified
    if category:
        resource = base / category
    else:
        resource = base

    # Traverse name parts (handles nested paths like "recipes/01-mcp-direct-dispatch.md")
    for part in name.split("/"):
        resource = resource / part

    # Read template content
    try:
        content = resource.read_text(encoding="utf-8")
    except (FileNotFoundError, TypeError) as e:
        raise FileNotFoundError(
            f"Template '{category}/{name}' not found. Try: uv tool install -e . --force"
        ) from e

    # Validate non-empty
    content = content.strip()
    if not content:
        raise ValueError(f"Template '{category}/{name}' is empty")

    return content


def list_all_templates() -> dict[str, list[dict[str, str]]]:
    """List all available templates with their metadata.

    Returns:
        Dictionary with "templates" key containing list of template metadata
    """
    templates = []
    for entry in TEMPLATE_REGISTRY:
        category = entry["category"]
        name = entry["name"]

        # Build URI: nano-agent://templates/{category}/{name} or nano-agent://templates/{name} for top-level
        if category:
            uri = f"{RESOURCE_URI_PREFIX}{category}/{name}"
        else:
            uri = f"{RESOURCE_URI_PREFIX}{name}"

        templates.append(
            {
                "uri": uri,
                "category": category,
                "name": name,
                "description": entry["description"],
            }
        )

    return {"templates": templates}


def _make_template_loader(category: str, name: str) -> Callable[[], str]:
    """Create a template loader function with proper __name__ attribute.

    Args:
        category: Template category
        name: Template file name

    Returns:
        Callable that loads the template
    """

    def _loader() -> str:
        return load_template(category, name)

    # Set proper __name__ for FastMCP introspection
    safe_name = f"{category}_{name}".replace("/", "_").replace(".", "_").replace("-", "_")
    _loader.__name__ = f"template_loader_{safe_name}"
    return _loader


def register_template_resources(mcp: Any) -> int:
    """Register all template resources with the MCP server.

    Args:
        mcp: FastMCP server instance

    Returns:
        Number of resources registered
    """
    count = 0

    # Register individual template resources
    for entry in TEMPLATE_REGISTRY:
        # Only register markdown files
        if not entry["name"].endswith(".md"):
            continue

        category = entry["category"]
        name = entry["name"]

        # Build URI
        if category:
            uri = f"{RESOURCE_URI_PREFIX}{category}/{name}"
        else:
            uri = f"{RESOURCE_URI_PREFIX}{name}"

        # Register with error isolation
        try:
            # Create loader function with proper __name__
            loader_func = _make_template_loader(category, name)

            # Register the resource using the decorator pattern
            mcp.resource(
                uri, mime_type=entry["mime_type"], description=entry["description"]
            )(loader_func)
            count += 1
        except Exception as e:
            logger.warning(f"Failed to register template resource {uri}: {e}")

    # Register index resource
    try:

        def _template_index() -> str:
            import json

            return json.dumps(list_all_templates(), indent=2)

        mcp.resource(
            f"{RESOURCE_URI_PREFIX}index",
            mime_type="application/json",
            description="Index of all available nano-agent templates",
        )(_template_index)

        count += 1
    except Exception as e:
        logger.warning(f"Failed to register template index resource: {e}")

    logger.info(f"Registered {count} template resources")
    return count
