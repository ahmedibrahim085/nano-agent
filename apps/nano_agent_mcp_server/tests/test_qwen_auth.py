"""
Tests for Qwen Cloud OAuth token management (qwen_auth module).

20 tests covering:
- Happy path (6 tests)
- Negative scenarios (6 tests)
- Edge cases (3 tests)
- Robustness (5 tests)
"""

import json
import time
import subprocess
from unittest.mock import patch, mock_open, MagicMock

import pytest

from nano_agent.modules.qwen_auth import (
    QwenAuthError,
    read_qwen_credentials,
    is_token_expired,
    refresh_token,
    save_credentials,
    get_valid_token,
)


# --- Fixtures ---

@pytest.fixture
def valid_creds():
    """Valid credentials dict with all required fields."""
    return {
        "access_token": "test_access_token_123",
        "refresh_token": "test_refresh_token_456",
        "expiry_date": int(time.time() * 1000) + 3600000,  # 1 hour ahead
    }


@pytest.fixture
def expired_creds():
    """Credentials with expired token."""
    return {
        "access_token": "old_access_token",
        "refresh_token": "test_refresh_token_456",
        "expiry_date": int(time.time() * 1000) - 3600000,  # 1 hour ago
    }


# --- Happy Path Tests (1-6) ---


class TestHappyPath:
    def test_read_credentials_success(self, valid_creds, tmp_path):
        """Test 1: Valid JSON with all required fields returns dict."""
        creds_file = tmp_path / "oauth_creds.json"
        creds_file.write_text(json.dumps(valid_creds))

        result = read_qwen_credentials(creds_path=creds_file)
        assert result["access_token"] == "test_access_token_123"
        assert result["refresh_token"] == "test_refresh_token_456"
        assert "expiry_date" in result

    def test_is_token_expired_not_expired(self, valid_creds):
        """Test 2: Token with expiry_date 1 hour ahead is NOT expired."""
        assert is_token_expired(valid_creds) is False

    def test_refresh_token_success(self, valid_creds):
        """Test 3: Mock subprocess returns valid JSON with new tokens."""
        refresh_response = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 21600,  # 6 hours in seconds
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(refresh_response)
        mock_result.stderr = ""

        with patch("shutil.which", return_value="/usr/bin/curl"):
            with patch("subprocess.run", return_value=mock_result):
                result = refresh_token(valid_creds)

        assert result["access_token"] == "new_access_token"
        assert result["refresh_token"] == "new_refresh_token"
        assert "expiry_date" in result
        # expiry_date should be approximately now + 21600*1000 ms
        expected_expiry = int(time.time() * 1000) + 21600 * 1000
        assert abs(result["expiry_date"] - expected_expiry) < 5000  # within 5s

    def test_save_credentials_writes_file(self, valid_creds, tmp_path):
        """Test 4: Writes JSON to file, verify content."""
        creds_file = tmp_path / "oauth_creds.json"
        save_credentials(valid_creds, creds_path=creds_file)

        saved = json.loads(creds_file.read_text())
        assert saved["access_token"] == valid_creds["access_token"]
        assert saved["refresh_token"] == valid_creds["refresh_token"]

    def test_get_valid_token_not_expired(self, valid_creds, tmp_path):
        """Test 5: Returns existing access_token when not expired, no refresh called."""
        creds_file = tmp_path / "oauth_creds.json"
        creds_file.write_text(json.dumps(valid_creds))

        with patch("nano_agent.modules.qwen_auth.refresh_token") as mock_refresh:
            token = get_valid_token(creds_path=creds_file)

        assert token == "test_access_token_123"
        mock_refresh.assert_not_called()

    def test_get_valid_token_expired_refreshes(self, expired_creds, tmp_path):
        """Test 6: Calls refresh, saves new creds, returns new token."""
        creds_file = tmp_path / "oauth_creds.json"
        creds_file.write_text(json.dumps(expired_creds))

        new_creds = {
            "access_token": "refreshed_token",
            "refresh_token": "new_refresh",
            "expiry_date": int(time.time() * 1000) + 3600000,
        }

        with patch("nano_agent.modules.qwen_auth.refresh_token", return_value=new_creds):
            with patch("nano_agent.modules.qwen_auth.save_credentials") as mock_save:
                token = get_valid_token(creds_path=creds_file)

        assert token == "refreshed_token"
        mock_save.assert_called_once()


# --- Negative Scenario Tests (7-12) ---


class TestNegativeScenarios:
    def test_read_credentials_file_not_found(self, tmp_path):
        """Test 7: Non-existent file raises QwenAuthError."""
        missing = tmp_path / "nonexistent.json"
        with pytest.raises(QwenAuthError, match="not found"):
            read_qwen_credentials(creds_path=missing)

    def test_read_credentials_malformed_json(self, tmp_path):
        """Test 8: Malformed JSON raises QwenAuthError."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json")
        with pytest.raises(QwenAuthError, match="invalid JSON"):
            read_qwen_credentials(creds_path=bad_file)

    def test_read_credentials_missing_access_token(self, tmp_path):
        """Test 9: JSON without access_token raises QwenAuthError."""
        creds_file = tmp_path / "creds.json"
        creds_file.write_text(json.dumps({"refresh_token": "tok"}))
        with pytest.raises(QwenAuthError, match="missing access_token"):
            read_qwen_credentials(creds_path=creds_file)

    def test_refresh_token_curl_failure(self, valid_creds):
        """Test 10: curl returncode=1 raises QwenAuthError."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "curl: (6) Could not resolve host"

        with patch("shutil.which", return_value="/usr/bin/curl"):
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(QwenAuthError):
                    refresh_token(valid_creds)

    def test_refresh_token_non_json_response(self, valid_creds):
        """Test 11: HTML response body raises QwenAuthError."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "<html><body>WAF Challenge</body></html>"
        mock_result.stderr = ""

        with patch("shutil.which", return_value="/usr/bin/curl"):
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(QwenAuthError):
                    refresh_token(valid_creds)

    def test_refresh_token_missing_access_token(self, valid_creds):
        """Test 12: JSON response without access_token raises QwenAuthError."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"error": "invalid_grant"})
        mock_result.stderr = ""

        with patch("shutil.which", return_value="/usr/bin/curl"):
            with patch("subprocess.run", return_value=mock_result):
                with pytest.raises(QwenAuthError):
                    refresh_token(valid_creds)


# --- Edge Case Tests (13-15) ---


class TestEdgeCases:
    def test_is_token_expired_expired(self):
        """Test 13: Token with expiry_date 1 hour ago IS expired."""
        creds = {
            "access_token": "tok",
            "refresh_token": "ref",
            "expiry_date": int(time.time() * 1000) - 3600000,
        }
        assert is_token_expired(creds) is True

    def test_is_token_expired_within_buffer(self):
        """Test 14: Token expiring in 3 min (inside 5-min buffer) IS expired."""
        creds = {
            "access_token": "tok",
            "refresh_token": "ref",
            "expiry_date": int(time.time() * 1000) + 3 * 60 * 1000,  # 3 min ahead
        }
        assert is_token_expired(creds) is True

    def test_is_token_expired_missing_expiry(self):
        """Test 15: No expiry_date key means expired (safe default)."""
        creds = {"access_token": "tok", "refresh_token": "ref"}
        assert is_token_expired(creds) is True


# --- Robustness Tests (16-20) ---


class TestRobustness:
    def test_refresh_token_timeout(self, valid_creds):
        """Test 16: subprocess.TimeoutExpired raises QwenAuthError with 'timed out'."""
        with patch("shutil.which", return_value="/usr/bin/curl"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="curl", timeout=15)):
                with pytest.raises(QwenAuthError, match="timed out"):
                    refresh_token(valid_creds)

    def test_refresh_token_curl_not_found(self, valid_creds):
        """Test 17: shutil.which returns None raises QwenAuthError with 'curl not found'."""
        with patch("shutil.which", return_value=None):
            with pytest.raises(QwenAuthError, match="curl not found"):
                refresh_token(valid_creds)

    def test_read_credentials_missing_refresh_token(self, tmp_path):
        """Test 18: JSON with access_token but no refresh_token raises QwenAuthError."""
        creds_file = tmp_path / "creds.json"
        creds_file.write_text(json.dumps({"access_token": "tok"}))
        with pytest.raises(QwenAuthError, match="missing refresh_token"):
            read_qwen_credentials(creds_path=creds_file)

    def test_save_credentials_atomic_write(self, valid_creds, tmp_path):
        """Test 19: Verify writes to .tmp first, then os.rename called."""
        creds_file = tmp_path / "oauth_creds.json"

        with patch("os.rename") as mock_rename:
            with patch("builtins.open", mock_open()):
                save_credentials(valid_creds, creds_path=creds_file)

        # Verify os.rename was called with .tmp → target path
        mock_rename.assert_called_once()
        args = mock_rename.call_args[0]
        assert str(args[0]).endswith(".tmp")
        assert str(args[1]) == str(creds_file)

    def test_get_valid_token_refresh_fails_raises(self, expired_creds, tmp_path):
        """Test 20: QwenAuthError from refresh_token propagates up."""
        creds_file = tmp_path / "oauth_creds.json"
        creds_file.write_text(json.dumps(expired_creds))

        with patch("nano_agent.modules.qwen_auth.refresh_token", side_effect=QwenAuthError("refresh failed")):
            with pytest.raises(QwenAuthError, match="refresh failed"):
                get_valid_token(creds_path=creds_file)
