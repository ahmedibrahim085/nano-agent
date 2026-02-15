"""
Tests for Nano Agent MCP Server Tools.

These are integration tests that use the smallest available Ollama model.
"""

import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from nano_agent.modules.nano_agent import (
    _execute_nano_agent,
    prompt_nano_agent,
    validate_model_provider_combination,
    get_agent_status
)
from nano_agent.modules.data_types import PromptNanoAgentRequest

from conftest import ollama_available


@pytest.mark.skipif(not ollama_available(), reason="No Ollama models available")
class TestExecuteNanoAgent:
    """Test the internal _execute_nano_agent function with real Ollama calls."""

    def test_execute_nano_agent_success(self, ollama_model):
        """Test successful execution with valid request."""
        request = PromptNanoAgentRequest(
            agentic_prompt="Say 'Hello, World!' in exactly 2 words",
            model=ollama_model,
            provider="ollama"
        )

        response = _execute_nano_agent(request)

        assert response.success is True
        assert response.error is None
        assert response.result is not None
        assert len(response.result) > 0
        assert response.metadata["model"] == ollama_model
        assert response.metadata["provider"] == "ollama"
        assert response.execution_time_seconds >= 0

    def test_execute_nano_agent_with_tools(self, ollama_model):
        """Test execution that uses tools."""
        request = PromptNanoAgentRequest(
            agentic_prompt="List the current directory",
            model=ollama_model,
            provider="ollama"
        )

        response = _execute_nano_agent(request)

        assert response.success is True
        assert "turns_used" in response.metadata

    def test_execute_nano_agent_different_models(self, ollama_model):
        """Test execution with the available Ollama model."""
        request = PromptNanoAgentRequest(
            agentic_prompt="What is 2+2? Answer with just the number.",
            model=ollama_model,
            provider="ollama"
        )

        response = _execute_nano_agent(request)

        assert response.success is True


class TestPromptNanoAgentTool:
    """Test the MCP tool prompt_nano_agent with real API."""

    @pytest.mark.asyncio
    @pytest.mark.skipif(not ollama_available(), reason="No Ollama models available")
    async def test_prompt_nano_agent_basic(self, ollama_model):
        """Test basic execution without context."""
        result = await prompt_nano_agent(
            agentic_prompt="What is 1+1? Answer with just the number.",
            model=ollama_model,
            provider="ollama"
        )

        assert result["success"] is True
        assert "error" not in result or result["error"] is None
        assert result["execution_time_seconds"] >= 0

    @pytest.mark.asyncio
    @pytest.mark.skipif(not ollama_available(), reason="No Ollama models available")
    async def test_prompt_nano_agent_default_parameters(self, ollama_model):
        """Test execution with explicit model (no reliance on cloud defaults)."""
        result = await prompt_nano_agent(
            agentic_prompt="Say hello",
            model=ollama_model,
            provider="ollama"
        )

        assert result["success"] is True
        assert result["result"] is not None

    @pytest.mark.asyncio
    async def test_prompt_nano_agent_invalid_provider(self):
        """Test error handling for invalid provider."""
        result = await prompt_nano_agent(
            agentic_prompt="Test",
            provider="invalid_provider"
        )

        assert result["success"] is False
        assert "input should be" in result["error"].lower()


class TestUtilityFunctions:
    """Test utility functions."""

    def test_validate_model_provider_combination_valid(self):
        """Test validation of valid model-provider combinations."""
        valid_combos = [
            ("gpt-5-mini", "openai"),
            ("gpt-5-nano", "openai"),
            ("gpt-5", "openai"),
        ]

        for model, provider in valid_combos:
            assert validate_model_provider_combination(model, provider) is True

    def test_validate_model_provider_combination_invalid(self):
        """Test validation of invalid model-provider combinations."""
        invalid_combos = [
            ("gpt-5", "anthropic"),  # Wrong provider
            ("claude-3-opus", "openai"),  # Wrong provider
            ("gpt-6", "openai"),  # Non-existent model
        ]

        for model, provider in invalid_combos:
            assert validate_model_provider_combination(model, provider) is False

    @pytest.mark.asyncio
    async def test_get_agent_status(self):
        """Test agent status retrieval."""
        status = await get_agent_status()

        assert status["status"] == "operational"
        assert status["version"] == "1.0.0"
        assert "gpt-5-mini" in status["available_models"]["openai"]
        assert "openai" in status["available_providers"]
        assert len(status["available_providers"]) >= 3
        assert "read_file" in status["tools_available"]
        assert "write_file" in status["tools_available"]
        assert len(status["tools_available"]) == 13


@pytest.mark.skipif(not ollama_available(), reason="No Ollama models available")
class TestIntegration:
    """Integration tests for the MCP tools with real Ollama API."""

    @pytest.mark.asyncio
    async def test_simple_task(self, ollama_model):
        """Test a simple task."""
        result = await prompt_nano_agent(
            agentic_prompt="What is the capital of France? Answer with just the city name.",
            model=ollama_model,
            provider="ollama"
        )

        assert result["success"] is True
        assert result["execution_time_seconds"] >= 0
        assert "model" in result["metadata"]
