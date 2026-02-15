#!/usr/bin/env python
"""Nano Agent MCP Server - Main entry point."""

import logging
import setproctitle
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load environment variables from .env file
load_dotenv()

# Import our nano agent tool (after load_dotenv so env vars are available at import time)
from .modules.nano_agent import prompt_nano_agent, launch_agent, check_providers  # noqa: E402
from .modules.constants import MCP_SERVER_INSTRUCTIONS  # noqa: E402
from .modules.template_resources import register_template_resources  # noqa: E402

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the MCP server instance
mcp = FastMCP(name="nano-agent", instructions=MCP_SERVER_INSTRUCTIONS)

# Register the nano agent tool
mcp.tool()(prompt_nano_agent)
mcp.tool()(launch_agent)
mcp.tool()(check_providers)

# Register template resources for MCP discovery
register_template_resources(mcp)


def run():
    """Entry point for the nano-agent command."""
    try:
        setproctitle.setproctitle("nano-agent-mcp")
        logger.info("Starting Nano Agent MCP Server...")
        # FastMCP.run() handles its own async context with anyio
        # Don't wrap it in asyncio.run()
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    run()
