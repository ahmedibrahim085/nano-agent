"""File-based MCP action logging.

When nano-agent runs as an MCP server (e.g. invoked from Claude Code), stdout is
consumed by the MCP protocol — so the regular rich-logging hooks are disabled
and there's nothing on disk to inspect when something hangs or times out.

This module writes structured JSON-lines records to
``~/.nano-agent/logs/mcp-actions.log`` regardless of the invocation path, so we
have a durable trace when something goes wrong.

Idempotent setup; safe to call from multiple entry points.
"""
import json
import logging
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

LOG_DIR = Path.home() / ".nano-agent" / "logs"
LOG_FILE = LOG_DIR / "mcp-actions.log"
_LOGGER_NAME = "nano_agent.mcp_actions"
_MAX_BYTES = 50 * 1024 * 1024  # 50 MB before rotation
_BACKUP_COUNT = 3

_logger: Optional[logging.Logger] = None


def setup_mcp_action_log() -> logging.Logger:
    """Configure the rotating file logger. Idempotent."""
    global _logger
    if _logger is not None:
        return _logger
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(_LOGGER_NAME)
    log.setLevel(logging.INFO)
    log.propagate = False
    if not log.handlers:
        handler = RotatingFileHandler(
            LOG_FILE, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
        )
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))
        log.addHandler(handler)
    _logger = log
    log.info(json.dumps({
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "action": "mcp_logging.setup",
        "log_file": str(LOG_FILE),
    }))
    return log


def log_action(action: str, **fields: Any) -> None:
    """Emit one JSON-lines record. Never raises."""
    log = _logger or setup_mcp_action_log()
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "action": action,
    }
    record.update(fields)
    try:
        line = json.dumps(record, default=str, ensure_ascii=False)
    except Exception:
        line = json.dumps({
            "ts": record["ts"],
            "action": action,
            "log_error": "json_encode_failed",
        })
    log.info(line)
