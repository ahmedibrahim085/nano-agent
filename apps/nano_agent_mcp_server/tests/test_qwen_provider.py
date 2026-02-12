"""
Tests for Qwen Cloud provider integration.

Tests cover:
- create_agent() Qwen branch (3 tests)
- validate_provider_setup() sync (3 tests)
- validate_provider_setup_async() (3 tests)
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from nano_agent.modules.provider_config import ProviderConfig
from nano_agent.modules.constants import (
    QWEN_BASE_URL,
    QWEN_AVAILABLE_MODELS,
    AVAILABLE_MODELS,
    PROVIDER_REQUIREMENTS,
)
from nano_agent.modules.qwen_auth import QwenAuthError


# --- create_agent Tests (1-3) ---


class TestCreateAgentQwen:
    def test_create_agent_qwen(self):
        """Verify Qwen agent uses AsyncOpenAI + OpenAIChatCompletionsModel."""
        with patch("nano_agent.modules.provider_config.AsyncOpenAI") as mock_async_openai, \
             patch("nano_agent.modules.provider_config.OpenAIChatCompletionsModel") as mock_model, \
             patch("nano_agent.modules.provider_config.Agent") as mock_agent, \
             patch("nano_agent.modules.qwen_auth.get_valid_token", return_value="test_token"):

            mock_client = MagicMock()
            mock_async_openai.return_value = mock_client
            mock_model_instance = MagicMock()
            mock_model.return_value = mock_model_instance

            ProviderConfig.create_agent(
                name="TestAgent",
                instructions="test",
                tools=[],
                model="coder-model",
                provider="qwen",
            )

            # Verify AsyncOpenAI called with correct params
            mock_async_openai.assert_called_once_with(
                base_url=QWEN_BASE_URL,
                api_key="test_token",
            )
            # Verify model wrapper created correctly
            mock_model.assert_called_once_with(
                model="coder-model",
                openai_client=mock_client,
            )
            # Verify Agent created
            mock_agent.assert_called_once()

    def test_create_agent_qwen_auth_error(self):
        """QwenAuthError from get_valid_token propagates up."""
        with patch("nano_agent.modules.qwen_auth.get_valid_token",
                    side_effect=QwenAuthError("token expired")):
            with pytest.raises(QwenAuthError, match="token expired"):
                ProviderConfig.create_agent(
                    name="TestAgent",
                    instructions="test",
                    tools=[],
                    model="coder-model",
                    provider="qwen",
                )

    def test_create_agent_qwen_model_settings_passed(self):
        """model_settings kwarg is forwarded to Agent constructor."""
        from agents import ModelSettings

        ms = ModelSettings(temperature=0.7, max_tokens=65536)

        with patch("nano_agent.modules.provider_config.AsyncOpenAI"), \
             patch("nano_agent.modules.provider_config.OpenAIChatCompletionsModel"), \
             patch("nano_agent.modules.provider_config.Agent") as mock_agent, \
             patch("nano_agent.modules.qwen_auth.get_valid_token", return_value="tok"):

            ProviderConfig.create_agent(
                name="TestAgent",
                instructions="test",
                tools=[],
                model="coder-model",
                provider="qwen",
                model_settings=ms,
            )

            call_kwargs = mock_agent.call_args[1]
            assert call_kwargs["model_settings"] is ms


# --- validate_provider_setup Tests (4-6) ---


class TestValidateSetupQwen:
    def test_validate_setup_qwen_valid(self):
        """Valid model + existing creds file → (True, None)."""
        with patch("nano_agent.modules.qwen_auth.QWEN_CREDS_PATH") as mock_path:
            mock_path.exists.return_value = True

            ok, err = ProviderConfig.validate_provider_setup(
                "qwen", "coder-model", AVAILABLE_MODELS, PROVIDER_REQUIREMENTS
            )

        assert ok is True
        assert err is None

    def test_validate_setup_qwen_invalid_model(self):
        """Unknown model → (False, error)."""
        ok, err = ProviderConfig.validate_provider_setup(
            "qwen", "nonexistent", AVAILABLE_MODELS, PROVIDER_REQUIREMENTS
        )
        assert ok is False
        assert "not available" in err

    def test_validate_setup_qwen_no_creds(self):
        """Missing creds file → (False, error)."""
        with patch("nano_agent.modules.qwen_auth.QWEN_CREDS_PATH") as mock_path:
            mock_path.exists.return_value = False

            ok, err = ProviderConfig.validate_provider_setup(
                "qwen", "coder-model", AVAILABLE_MODELS, PROVIDER_REQUIREMENTS
            )

        assert ok is False
        assert "not found" in err


# --- validate_provider_setup_async Tests (7-9) ---


class TestValidateSetupAsyncQwen:
    @pytest.mark.asyncio
    async def test_validate_setup_async_qwen_valid(self):
        """Async: valid model + existing creds → (True, None)."""
        with patch("nano_agent.modules.qwen_auth.QWEN_CREDS_PATH") as mock_path:
            mock_path.exists.return_value = True

            ok, err = await ProviderConfig.validate_provider_setup_async(
                "qwen", "coder-model", AVAILABLE_MODELS, PROVIDER_REQUIREMENTS
            )

        assert ok is True
        assert err is None

    @pytest.mark.asyncio
    async def test_validate_setup_async_qwen_invalid_model(self):
        """Async: unknown model → (False, error)."""
        ok, err = await ProviderConfig.validate_provider_setup_async(
            "qwen", "nonexistent", AVAILABLE_MODELS, PROVIDER_REQUIREMENTS
        )
        assert ok is False
        assert "not available" in err

    @pytest.mark.asyncio
    async def test_validate_setup_async_qwen_no_creds(self):
        """Async: missing creds file → (False, error)."""
        with patch("nano_agent.modules.qwen_auth.QWEN_CREDS_PATH") as mock_path:
            mock_path.exists.return_value = False

            ok, err = await ProviderConfig.validate_provider_setup_async(
                "qwen", "coder-model", AVAILABLE_MODELS, PROVIDER_REQUIREMENTS
            )

        assert ok is False
        assert "not found" in err
