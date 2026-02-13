"""Test that setproctitle works correctly."""

import setproctitle


def test_setproctitle():
    setproctitle.setproctitle("nano-agent-mcp")
    assert setproctitle.getproctitle() == "nano-agent-mcp"
