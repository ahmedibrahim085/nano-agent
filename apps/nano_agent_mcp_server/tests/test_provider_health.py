"""
Tests for Provider Health Check feature (US-002).

Tests cover all provider states (up, down, partial), timeout handling,
401/403 errors, and concurrent execution.
"""

import pytest
import os
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Dict, Any

import httpx

from nano_agent.modules.provider_config import _check_provider_health, check_all_providers_async
from nano_agent.modules.data_types import ProviderHealthStatus, CheckProvidersResponse
from nano_agent.modules.constants import AVAILABLE_MODELS, ZAI_AVAILABLE_MODELS


# ============================================================================
# OpenAI Tests
# ============================================================================

@pytest.mark.asyncio
async def test_check_provider_health_openai_up():
    """Verify OpenAI up state with 200 response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"id": "gpt-5"},
            {"id": "gpt-5-mini"},
            {"id": "gpt-5-nano"},
            {"id": "gpt-4o"}
        ]
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("os.getenv", return_value="sk-test-key"):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            result = await _check_provider_health("openai")

    assert result.status == "up"
    assert len(result.available_models) == 4
    assert "gpt-5" in result.available_models
    assert result.latency_ms > 0
    assert result.error is None


@pytest.mark.asyncio
async def test_check_provider_health_openai_down_invalid_key():
    """Verify OpenAI down with 401/403."""
    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("os.getenv", return_value="sk-invalid-key"):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            result = await _check_provider_health("openai")

    assert result.status == "down"
    assert result.available_models == []
    assert result.error == "API key invalid"
    assert result.latency_ms > 0


@pytest.mark.asyncio
async def test_check_provider_health_openai_down_unreachable():
    """Verify OpenAI down with connection error."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")

    with patch("os.getenv", return_value="sk-test-key"):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            result = await _check_provider_health("openai")

    assert result.status == "down"
    assert result.available_models == []
    assert result.error == "endpoint unreachable"
    assert result.latency_ms is None


@pytest.mark.asyncio
async def test_check_provider_health_openai_timeout():
    """Verify OpenAI timeout handling."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.TimeoutException("Request timed out")

    with patch("os.getenv", return_value="sk-test-key"):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            result = await _check_provider_health("openai")

    assert result.status == "down"
    assert result.available_models == []
    assert result.error == "openai endpoint timeout"
    assert result.latency_ms is None


@pytest.mark.asyncio
async def test_check_provider_health_openai_missing_key():
    """Verify OpenAI down with missing API key."""
    with patch("os.getenv", return_value=None):
        result = await _check_provider_health("openai")

    assert result.status == "down"
    assert result.available_models == []
    assert "Missing environment variable: OPENAI_API_KEY" in result.error


# ============================================================================
# Anthropic Tests
# ============================================================================

@pytest.mark.asyncio
async def test_check_provider_health_anthropic_up():
    """Verify Anthropic up with static list (no endpoint ping)."""
    with patch("os.getenv", return_value="sk-ant-test-key"):
        result = await _check_provider_health("anthropic")

    assert result.status == "up"
    assert result.available_models == AVAILABLE_MODELS["anthropic"]
    assert result.latency_ms >= 0
    assert result.error is None


@pytest.mark.asyncio
async def test_check_provider_health_anthropic_down_missing_key():
    """Verify Anthropic down with missing key."""
    with patch("os.getenv", return_value=None):
        result = await _check_provider_health("anthropic")

    assert result.status == "down"
    assert result.available_models == []
    assert "Missing environment variable: ANTHROPIC_API_KEY" in result.error


# ============================================================================
# Z.ai Tests
# ============================================================================

@pytest.mark.asyncio
async def test_check_provider_health_zai_up():
    """Verify Z.ai up with static list (no endpoint ping)."""
    with patch("os.getenv", return_value="zai-test-key"):
        result = await _check_provider_health("zai")

    assert result.status == "up"
    assert result.available_models == ZAI_AVAILABLE_MODELS
    assert result.latency_ms >= 0
    assert result.error is None


@pytest.mark.asyncio
async def test_check_provider_health_zai_down_missing_key():
    """Verify Z.ai down with missing key."""
    with patch("os.getenv", return_value=None):
        result = await _check_provider_health("zai")

    assert result.status == "down"
    assert result.available_models == []
    assert "Missing environment variable: Z_AI_API_KEY" in result.error


# ============================================================================
# Ollama Tests
# ============================================================================

@pytest.mark.asyncio
async def test_check_provider_health_ollama_up():
    """Verify Ollama up with all models."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "models": [
            {"name": "gpt-oss:20b"},
            {"name": "gpt-oss:120b"},
            {"name": "qwen3-coder:30b"},
            {"name": "gemma3:27b"},
            {"name": "magistral:latest"}
        ]
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = mock_client
        result = await _check_provider_health("ollama")

    assert result.status == "up"
    assert len(result.available_models) == 5
    assert "gpt-oss:20b" in result.available_models
    assert result.latency_ms > 0
    assert result.error is None


@pytest.mark.asyncio
async def test_check_provider_health_ollama_partial():
    """Verify Ollama partial with subset of models."""
    mock_response = MagicMock()
    # Only 2 of 5 expected models
    mock_response.json.return_value = {
        "models": [
            {"name": "gpt-oss:20b"},
            {"name": "qwen3-coder:30b"}
        ]
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = mock_client
        result = await _check_provider_health("ollama")

    assert result.status == "partial"
    assert len(result.available_models) == 2
    assert "gpt-oss:20b" in result.available_models
    assert result.latency_ms > 0
    assert result.error is None


@pytest.mark.asyncio
async def test_check_provider_health_ollama_down():
    """Verify Ollama down when service not running."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = mock_client
        result = await _check_provider_health("ollama")

    assert result.status == "down"
    assert result.available_models == []
    assert "service not running" in result.error
    assert "ollama serve" in result.error


@pytest.mark.asyncio
async def test_check_provider_health_ollama_empty_models():
    """Verify Ollama down with no models loaded."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"models": []}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = mock_client
        result = await _check_provider_health("ollama")

    assert result.status == "down"
    assert result.available_models == []
    assert result.latency_ms > 0
    assert result.error is None


# ============================================================================
# LM Studio Tests
# ============================================================================

@pytest.mark.asyncio
async def test_check_provider_health_lmstudio_up():
    """Verify LM Studio up state."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "data": [
            {"id": "qwen3-coder-next"},
            {"id": "gpt-oss:20b"}
        ]
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = mock_client
        result = await _check_provider_health("lmstudio")

    assert result.status == "up"
    assert len(result.available_models) == 2
    assert "qwen3-coder-next" in result.available_models
    assert result.latency_ms > 0
    assert result.error is None


@pytest.mark.asyncio
async def test_check_provider_health_lmstudio_down():
    """Verify LM Studio down when service not running."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectError("Connection refused")

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = mock_client
        result = await _check_provider_health("lmstudio")

    assert result.status == "down"
    assert result.available_models == []
    assert "service not running" in result.error
    assert "LM Studio app" in result.error


# ============================================================================
# Concurrent Execution Tests
# ============================================================================

@pytest.mark.asyncio
async def test_check_all_providers_async_concurrent():
    """Verify all 5 providers checked concurrently."""
    # Mock all providers to be up
    async def mock_check(provider):
        await asyncio.sleep(0.1)  # Simulate some delay
        return ProviderHealthStatus(
            status="up",
            available_models=["model1"],
            latency_ms=100
        )

    with patch("nano_agent.modules.provider_config._check_provider_health", side_effect=mock_check):
        result = await check_all_providers_async()

    assert result.success is True
    assert len(result.providers) == 6
    assert "openai" in result.providers
    assert "anthropic" in result.providers
    assert "ollama" in result.providers
    assert "lmstudio" in result.providers
    assert "zai" in result.providers
    assert "qwen" in result.providers
    # Total time should be close to 100ms (max of individual), not 500ms (sum)
    assert result.total_check_time_ms < 200  # Should be ~100ms, not 500ms


@pytest.mark.asyncio
async def test_check_all_providers_async_response_schema():
    """Verify response matches CheckProvidersResponse."""
    async def mock_check(provider):
        return ProviderHealthStatus(
            status="up",
            available_models=["model1"],
            latency_ms=50
        )

    with patch("nano_agent.modules.provider_config._check_provider_health", side_effect=mock_check):
        result = await check_all_providers_async()

    assert isinstance(result, CheckProvidersResponse)
    assert hasattr(result, "success")
    assert hasattr(result, "providers")
    assert hasattr(result, "total_check_time_ms")
    assert hasattr(result, "providers_up")
    assert hasattr(result, "providers_down")
    assert hasattr(result, "providers_partial")


@pytest.mark.asyncio
async def test_check_all_providers_async_counters():
    """Verify up/down/partial counters accurate."""
    async def mock_check(provider):
        if provider == "openai":
            return ProviderHealthStatus(status="up", available_models=["gpt-5"], latency_ms=100)
        elif provider == "anthropic":
            return ProviderHealthStatus(status="down", available_models=[], error="No key")
        elif provider == "ollama":
            return ProviderHealthStatus(status="partial", available_models=["model1"], latency_ms=50)
        elif provider == "lmstudio":
            return ProviderHealthStatus(status="up", available_models=["model2"], latency_ms=50)
        elif provider == "zai":
            return ProviderHealthStatus(status="down", available_models=[], error="No key")
        else:  # qwen
            return ProviderHealthStatus(status="up", available_models=["coder-model"], latency_ms=1)

    with patch("nano_agent.modules.provider_config._check_provider_health", side_effect=mock_check):
        result = await check_all_providers_async()

    assert result.providers_up == 3
    assert result.providers_down == 2
    assert result.providers_partial == 1
    assert result.providers_up + result.providers_down + result.providers_partial == 6


@pytest.mark.asyncio
async def test_check_all_providers_async_total_time():
    """Verify total time is max of individual times."""
    async def mock_check(provider):
        # Different latencies per provider
        latencies = {
            "openai": 200,
            "anthropic": 1,
            "ollama": 50,
            "lmstudio": 40,
            "zai": 1,
            "qwen": 1,
        }
        await asyncio.sleep(latencies[provider] / 1000)  # Convert to seconds
        return ProviderHealthStatus(
            status="up",
            available_models=["model1"],
            latency_ms=latencies[provider]
        )

    with patch("nano_agent.modules.provider_config._check_provider_health", side_effect=mock_check):
        result = await check_all_providers_async()

    # Total time should be close to max individual time (200ms), not sum (292ms)
    assert result.total_check_time_ms >= 200
    assert result.total_check_time_ms < 250  # Should be ~200ms, not ~292ms


@pytest.mark.asyncio
async def test_check_all_providers_async_one_exception():
    """Verify one provider exception doesn't abort others."""
    async def mock_check(provider):
        if provider == "openai":
            raise Exception("OpenAI failed")
        return ProviderHealthStatus(
            status="up",
            available_models=["model1"],
            latency_ms=50
        )

    with patch("nano_agent.modules.provider_config._check_provider_health", side_effect=mock_check):
        result = await check_all_providers_async()

    assert result.success is True
    assert result.providers["openai"].status == "down"
    assert "OpenAI failed" in result.providers["openai"].error
    # Other providers should succeed
    assert result.providers["anthropic"].status == "up"
    assert result.providers["zai"].status == "up"
    assert result.providers_up == 5
    assert result.providers_down == 1


@pytest.mark.asyncio
async def test_check_all_providers_async_all_down():
    """Verify all providers down scenario."""
    async def mock_check(provider):
        return ProviderHealthStatus(
            status="down",
            available_models=[],
            error=f"{provider} unavailable"
        )

    with patch("nano_agent.modules.provider_config._check_provider_health", side_effect=mock_check):
        result = await check_all_providers_async()

    assert result.success is True  # Check succeeded, even though all providers are down
    assert result.providers_down == 6
    assert result.providers_up == 0
    assert result.providers_partial == 0
    for provider, status in result.providers.items():
        assert status.status == "down"


# ============================================================================
# MCP Tool Tests
# ============================================================================

@pytest.mark.asyncio
async def test_check_providers_mcp_tool():
    """Verify MCP tool calls orchestrator and returns dict."""
    from nano_agent.modules.nano_agent import check_providers

    mock_response = CheckProvidersResponse(
        success=True,
        providers={
            "openai": ProviderHealthStatus(status="up", available_models=["gpt-5"], latency_ms=100),
            "anthropic": ProviderHealthStatus(status="up", available_models=["claude"], latency_ms=1),
            "ollama": ProviderHealthStatus(status="up", available_models=["model"], latency_ms=50),
            "lmstudio": ProviderHealthStatus(status="up", available_models=["model"], latency_ms=40),
            "zai": ProviderHealthStatus(status="up", available_models=["glm"], latency_ms=1),
            "qwen": ProviderHealthStatus(status="up", available_models=["coder-model"], latency_ms=1),
        },
        total_check_time_ms=100,
        providers_up=6,
        providers_down=0,
        providers_partial=0
    )

    with patch("nano_agent.modules.nano_agent.check_all_providers_async", return_value=mock_response):
        result = await check_providers()

    assert isinstance(result, dict)
    assert result["success"] is True
    assert "providers" in result
    assert result["providers_up"] == 6
    assert len(result["providers"]) == 6


# ============================================================================
# Additional Coverage Tests
# ============================================================================

@pytest.mark.asyncio
async def test_check_provider_health_lmstudio_empty_models():
    """Verify LM Studio down with no models loaded."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": []}

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = mock_client
        result = await _check_provider_health("lmstudio")

    assert result.status == "down"
    assert result.available_models == []
    assert result.latency_ms > 0
    assert result.error is None


@pytest.mark.asyncio
async def test_check_provider_health_lmstudio_timeout():
    """Verify LM Studio timeout handling."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.TimeoutException("Request timed out")

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = mock_client
        result = await _check_provider_health("lmstudio")

    assert result.status == "down"
    assert result.available_models == []
    assert "service timeout" in result.error


@pytest.mark.asyncio
async def test_check_provider_health_ollama_timeout():
    """Verify Ollama timeout handling."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.TimeoutException("Request timed out")

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client_class.return_value.__aenter__.return_value = mock_client
        result = await _check_provider_health("ollama")

    assert result.status == "down"
    assert result.available_models == []
    assert "service timeout" in result.error


@pytest.mark.asyncio
async def test_check_provider_health_openai_unexpected_status():
    """Verify OpenAI down with unexpected HTTP status code (e.g. 500)."""
    mock_response = MagicMock()
    mock_response.status_code = 500

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response

    with patch("os.getenv", return_value="sk-test-key"):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client_class.return_value.__aenter__.return_value = mock_client
            result = await _check_provider_health("openai")

    assert result.status == "down"
    assert result.available_models == []
    assert "Unexpected status code: 500" in result.error
    assert result.latency_ms > 0


@pytest.mark.asyncio
async def test_check_providers_error_path():
    """Verify check_providers MCP tool returns error dict when orchestrator throws."""
    from nano_agent.modules.nano_agent import check_providers

    with patch("nano_agent.modules.nano_agent.check_all_providers_async", side_effect=RuntimeError("DB exploded")):
        result = await check_providers()

    assert isinstance(result, dict)
    assert result["success"] is False
    assert result["error"] == "DB exploded"
    assert result["providers"] == {}
    assert result["providers_up"] == 0
    assert result["providers_down"] == 0
    assert result["providers_partial"] == 0


@pytest.mark.asyncio
async def test_check_provider_health_unknown_provider():
    """Verify unknown provider returns down status."""
    result = await _check_provider_health("foobar")

    assert result.status == "down"
    assert result.available_models == []
    assert "Unknown provider: foobar" in result.error
