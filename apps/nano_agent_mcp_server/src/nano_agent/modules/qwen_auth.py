"""
Qwen Cloud OAuth token management.

Handles reading, validating, refreshing, and saving OAuth tokens
for Qwen Cloud API authentication. Token refresh uses curl subprocess
because Qwen's WAF blocks Python HTTP clients (httpx/requests).
"""

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Qwen OAuth constants
QWEN_CREDS_PATH = Path.home() / ".qwen" / "oauth_creds.json"
QWEN_REFRESH_URL = "https://chat.qwen.ai/api/v1/oauth2/token"
QWEN_CLIENT_ID = "f0304373b74a44d2b584a3fb70ca9e56"
EXPIRY_BUFFER_MS = 5 * 60 * 1000  # 5-minute safety buffer


class QwenAuthError(Exception):
    """Raised when Qwen OAuth authentication fails."""

    pass


def read_qwen_credentials(creds_path: Path = QWEN_CREDS_PATH) -> dict:
    """Read and validate Qwen OAuth credentials from JSON file.

    Args:
        creds_path: Path to the credentials JSON file.

    Returns:
        dict with access_token, refresh_token, and optionally expiry_date.

    Raises:
        QwenAuthError: If file not found, malformed JSON, or missing required keys.
    """
    if not creds_path.exists():
        raise QwenAuthError(f"Qwen credentials not found at {creds_path}")

    try:
        with open(creds_path) as f:
            creds = json.load(f)
    except json.JSONDecodeError:
        raise QwenAuthError(f"Qwen credentials contain invalid JSON at {creds_path}")

    if "access_token" not in creds:
        raise QwenAuthError("Qwen credentials missing access_token")
    if not isinstance(creds["access_token"], str) or not creds["access_token"].strip():
        raise QwenAuthError(
            f"Qwen credentials access_token is invalid "
            f"(type={type(creds['access_token']).__name__})"
        )

    if "refresh_token" not in creds:
        raise QwenAuthError("Qwen credentials missing refresh_token")
    if (
        not isinstance(creds["refresh_token"], str)
        or not creds["refresh_token"].strip()
    ):
        raise QwenAuthError(
            f"Qwen credentials refresh_token is invalid "
            f"(type={type(creds['refresh_token']).__name__})"
        )

    logger.debug("Read Qwen credentials from %s", creds_path)
    return creds


def is_token_expired(creds: dict, buffer_ms: int = EXPIRY_BUFFER_MS) -> bool:
    """Check if the OAuth token is expired or about to expire.

    Args:
        creds: Credentials dict with optional expiry_date (milliseconds epoch).
        buffer_ms: Safety buffer in milliseconds before actual expiry.

    Returns:
        True if token is expired or missing expiry_date (safe default).
    """
    expiry_date = creds.get("expiry_date")
    if expiry_date is None:
        logger.debug("No expiry_date in credentials — treating as expired")
        return True

    now_ms = int(time.time() * 1000)
    is_expired = now_ms >= (expiry_date - buffer_ms)
    logger.debug(
        "Token expiry check: now=%d, expiry=%d, buffer=%d, expired=%s",
        now_ms,
        expiry_date,
        buffer_ms,
        is_expired,
    )
    return is_expired


def refresh_token(
    creds: dict,
    refresh_url: str = QWEN_REFRESH_URL,
    client_id: str = QWEN_CLIENT_ID,
) -> dict:
    """Refresh the OAuth token using curl subprocess.

    Uses curl instead of Python HTTP clients because Qwen's WAF
    (Alibaba Cloud) blocks httpx/requests fingerprints.

    Args:
        creds: Current credentials dict (must contain refresh_token).
        refresh_url: Token refresh endpoint URL.
        client_id: OAuth client ID.

    Returns:
        New credentials dict with access_token, refresh_token, and expiry_date.

    Raises:
        QwenAuthError: If curl not found, timeout, non-zero exit, or invalid response.
    """
    if shutil.which("curl") is None:
        raise QwenAuthError("curl not found — required for Qwen token refresh")

    body = urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": creds["refresh_token"],
        }
    )

    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "POST",
                refresh_url,
                "-H",
                "Content-Type: application/x-www-form-urlencoded",
                "-d",
                body,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        raise QwenAuthError("Qwen token refresh timed out after 15s")

    if result.returncode != 0:
        logger.error("curl failed (rc=%d): %s", result.returncode, result.stderr)
        raise QwenAuthError(
            f"curl failed with exit code {result.returncode}: {result.stderr}"
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.error("Non-JSON response from refresh endpoint: %s", result.stdout[:200])
        raise QwenAuthError("Qwen token refresh returned non-JSON response")

    # Check for OAuth error response first
    if "error" in data:
        error_desc = data.get("error_description", data["error"])
        raise QwenAuthError(f"Qwen token refresh failed: {error_desc}")

    if "access_token" not in data:
        raise QwenAuthError(f"Qwen token refresh response missing access_token: {data}")

    # Compute expiry_date from expires_in (seconds → milliseconds)
    expires_in = data.get("expires_in")
    if expires_in is None:
        expires_in = 21600
        logger.warning(
            "Token refresh response missing expires_in — defaulting to %ds", expires_in
        )

    data["expiry_date"] = int(time.time() * 1000) + expires_in * 1000

    logger.debug("Token refreshed, new expiry in %ds", expires_in)
    return data


def save_credentials(creds: dict, creds_path: Path = QWEN_CREDS_PATH) -> None:
    """Save credentials to file using atomic write.

    Writes to a temporary file first, then atomically renames to prevent
    corruption from concurrent writes.

    Args:
        creds: Credentials dict to save.
        creds_path: Target file path.
    """
    tmp_path = creds_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w") as f:
            json.dump(creds, f, indent=2)
        os.rename(str(tmp_path), str(creds_path))
        logger.debug("Saved credentials to %s (atomic write)", creds_path)
    except Exception:
        # Clean up orphaned temp file on any failure
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def get_valid_token(creds_path: Path = QWEN_CREDS_PATH) -> str:
    """Get a valid Qwen OAuth access token, refreshing if needed.

    Orchestrates: read → check expiry → refresh if needed → save → return token.

    Args:
        creds_path: Path to credentials file.

    Returns:
        Valid access_token string.

    Raises:
        QwenAuthError: If credentials cannot be read or refresh fails.
    """
    creds = read_qwen_credentials(creds_path)

    if is_token_expired(creds):
        logger.info("Qwen token expired — refreshing")
        creds = refresh_token(creds)
        save_credentials(creds, creds_path)

    return creds["access_token"]
