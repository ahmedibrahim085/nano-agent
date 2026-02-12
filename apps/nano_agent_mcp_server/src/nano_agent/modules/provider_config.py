"""
Provider Configuration for Multi-Model Support.

This module provides a thin abstraction layer for creating agents
with different model providers (OpenAI, Anthropic, Ollama).
"""

from typing import Optional, Union
import os
import logging
import time
import asyncio
from openai import AsyncOpenAI
from agents import Agent, OpenAIChatCompletionsModel, ModelSettings, set_tracing_disabled
from agents.extensions.models.litellm_model import LitellmModel
import requests
import httpx

# Apply typing fixes for Python 3.12+ compatibility
from . import typing_fix

# Import data types for health check
from .data_types import ProviderHealthStatus, CheckProvidersResponse
from .constants import AVAILABLE_MODELS, ZAI_AVAILABLE_MODELS, get_model_capabilities

logger = logging.getLogger(__name__)

# Shared config for local providers: (base_url, endpoint, model_extractor, start_hint)
LOCAL_PROVIDER_CONFIG = {
    "ollama": ("http://127.0.0.1:11434", "/api/tags", lambda d: [m["name"] for m in d.get("models", [])], "ollama serve"),
    "lmstudio": ("http://127.0.0.1:1234", "/v1/models", lambda d: [m["id"] for m in d.get("data", [])], "LM Studio app"),
}


class ProviderConfig:
    """Configuration for different model providers."""
    
    @staticmethod
    def validate_tool_support(model: str) -> tuple[bool, str | None]:
        """Check if a model supports tool calling.

        Returns:
            (True, None) if model supports tools.
            (False, error_message) if model does NOT support tools.
        """
        caps = get_model_capabilities(model)
        if not caps.supports_tools:
            return False, (
                f"Model '{model}' does not support tool calling. "
                f"Choose a model with tool support (e.g., qwen3-coder:30b, gpt-5-mini)."
            )
        return True, None

    @staticmethod
    def get_model_settings(model: str, provider: str) -> ModelSettings:
        """Build ModelSettings from the per-model capabilities registry.

        Args:
            model: Model identifier (e.g., "glm-4.7", "gpt-5-mini")
            provider: Provider name (for logging only)

        Returns:
            ModelSettings configured for the specific model
        """
        caps = get_model_capabilities(model)

        settings = {}
        if caps.supports_temperature:
            settings["temperature"] = caps.temperature
        settings["max_tokens"] = caps.max_tokens
        if caps.top_p is not None:
            settings["top_p"] = caps.top_p
        if caps.parallel_tool_calls is not None:
            settings["parallel_tool_calls"] = caps.parallel_tool_calls
        if caps.frequency_penalty is not None:
            settings["frequency_penalty"] = caps.frequency_penalty
        if caps.presence_penalty is not None:
            settings["presence_penalty"] = caps.presence_penalty
        if caps.extra_body is not None:
            settings["extra_body"] = caps.extra_body

        logger.debug(f"Model settings for {model} ({provider}): {settings}")
        return ModelSettings(**settings)
    
    @staticmethod
    def create_agent(
        name: str,
        instructions: str,
        tools: list,
        model: str,
        provider: str,
        model_settings: Optional[ModelSettings] = None
    ) -> Agent:
        """Create an agent with the appropriate provider configuration.
        
        Args:
            name: Agent name
            instructions: System instructions for the agent
            tools: List of tool functions
            model: Model identifier
            provider: Provider name ('openai', 'anthropic', 'ollama', 'lmstudio', 'zai', 'qwen')
            model_settings: Optional model settings
            
        Returns:
            Configured Agent instance
            
        Raises:
            ValueError: If provider is not supported
        """
        
        if provider == "openai":
            # Default OpenAI configuration
            logger.debug(f"Creating OpenAI agent with model: {model}")
            return Agent(
                name=name,
                instructions=instructions,
                tools=tools,
                model=model,
                model_settings=model_settings
            )
        
        elif provider == "anthropic":
            # Use OpenAI SDK with Anthropic's OpenAI-compatible endpoint
            logger.debug(f"Creating Anthropic agent with model: {model}")
            anthropic_client = AsyncOpenAI(
                base_url="https://api.anthropic.com/v1/",
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
            return Agent(
                name=name,
                instructions=instructions,
                tools=tools,
                model=OpenAIChatCompletionsModel(
                    model=model,
                    openai_client=anthropic_client
                ),
                model_settings=model_settings
            )
        
        elif provider == "ollama":
            # Use OpenAI-compatible endpoint for Ollama
            logger.debug(f"Creating Ollama agent with model: {model}")
            ollama_client = AsyncOpenAI(
                base_url="http://127.0.0.1:11434/v1",
                api_key="ollama"  # Dummy key required by client
            )
            return Agent(
                name=name,
                instructions=instructions,
                tools=tools,
                model=OpenAIChatCompletionsModel(
                    model=model,
                    openai_client=ollama_client
                ),
                model_settings=model_settings
            )

        elif provider == "lmstudio":
            # Use OpenAI-compatible endpoint for LM Studio
            logger.debug(f"Creating LM Studio agent with model: {model}")
            lmstudio_client = AsyncOpenAI(
                base_url="http://127.0.0.1:1234/v1",
                api_key="lm-studio"  # Dummy key required by client
            )
            return Agent(
                name=name,
                instructions=instructions,
                tools=tools,
                model=OpenAIChatCompletionsModel(
                    model=model,
                    openai_client=lmstudio_client
                ),
                model_settings=model_settings
            )

        elif provider == "zai":
            # Z.ai uses Anthropic-compatible API — route via LiteLLM
            from .constants import ZAI_BASE_URL
            logger.debug(f"Creating Z.ai agent with model: {model}")
            zai_model = LitellmModel(
                model=f"anthropic/{model}",
                base_url=ZAI_BASE_URL,
                api_key=os.getenv("Z_AI_API_KEY")
            )
            return Agent(
                name=name,
                instructions=instructions,
                tools=tools,
                model=zai_model,
                model_settings=model_settings
            )

        elif provider == "qwen":
            # Qwen Cloud: OpenAI-compatible endpoint with OAuth token
            from .qwen_auth import get_valid_token
            from .constants import QWEN_BASE_URL
            logger.debug(f"Creating Qwen Cloud agent with model: {model}")
            token = get_valid_token()
            qwen_client = AsyncOpenAI(
                base_url=QWEN_BASE_URL,
                api_key=token,
            )
            return Agent(
                name=name,
                instructions=instructions,
                tools=tools,
                model=OpenAIChatCompletionsModel(
                    model=model,
                    openai_client=qwen_client,
                ),
                model_settings=model_settings,
            )

        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    @staticmethod
    def setup_provider(provider: str) -> None:
        """Setup provider-specific configurations.

        Args:
            provider: Provider name
        """
        # Disable tracing globally — it's a process-wide singleton that causes
        # race conditions when multiple agents with different providers run
        # concurrently. Disabling unconditionally eliminates the race.
        set_tracing_disabled(True)
    
    @staticmethod
    def validate_provider_setup(provider: str, model: str, available_models: dict, provider_requirements: dict) -> tuple[bool, Optional[str]]:
        """Validate that provider is properly configured.
        
        Args:
            provider: Provider name
            model: Model identifier
            available_models: Dictionary of available models per provider
            provider_requirements: Dictionary of API key requirements
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        
        # Z.ai: validate against known model list
        if provider == "zai":
            if model not in ZAI_AVAILABLE_MODELS:
                return False, f"Model '{model}' not available for Z.ai. Available: {', '.join(ZAI_AVAILABLE_MODELS)}"
            required_key = provider_requirements.get(provider)
            if required_key and not os.getenv(required_key):
                return False, f"Missing environment variable: {required_key}"
            return True, None

        # Qwen Cloud: validate model + credentials file
        if provider == "qwen":
            from .constants import QWEN_AVAILABLE_MODELS
            if model not in QWEN_AVAILABLE_MODELS:
                return False, f"Model '{model}' not available for Qwen Cloud. Available: {', '.join(QWEN_AVAILABLE_MODELS)}"
            from .qwen_auth import QWEN_CREDS_PATH
            if not QWEN_CREDS_PATH.exists():
                return False, f"Qwen OAuth credentials not found at {QWEN_CREDS_PATH}. Run 'qwen' CLI to authenticate first."
            return True, None

        if provider in LOCAL_PROVIDER_CONFIG:
            base_url, endpoint, extract_models, start_hint = LOCAL_PROVIDER_CONFIG[provider]
            try:
                response = requests.get(f"{base_url}{endpoint}", timeout=3)
                models = extract_models(response.json())
                if model not in models:
                    available = ", ".join(models[:10])
                    hint = f" (showing first 10)" if len(models) > 10 else ""
                    return False, f"Model '{model}' not found in {provider}. Available{hint}: {available}"
            except requests.ConnectionError:
                return False, f"{provider} service not running. Start with: {start_hint}"
            except requests.Timeout:
                return False, f"{provider} service timeout. Check if service is running"
            except Exception as e:
                return False, f"Error checking {provider} availability: {str(e)}"
        elif provider in available_models:
            # Cloud providers: check against static model list
            if model not in available_models[provider]:
                return False, f"Model {model} not available for {provider}. Available models: {', '.join(available_models[provider])}"
        else:
            return False, f"Unknown provider: {provider}. Available: {', '.join(list(available_models.keys()) + list(LOCAL_PROVIDER_CONFIG.keys()))}"

        # Check API keys
        required_key = provider_requirements.get(provider)
        if required_key and not os.getenv(required_key):
            return False, f"Missing environment variable: {required_key}"

        return True, None

    @staticmethod
    async def validate_provider_setup_async(provider: str, model: str, available_models: dict, provider_requirements: dict) -> tuple[bool, Optional[str]]:
        """Async version of validate_provider_setup. Uses httpx instead of requests.

        Args:
            provider: Provider name
            model: Model identifier
            available_models: Dictionary of available models per provider
            provider_requirements: Dictionary of API key requirements

        Returns:
            Tuple of (is_valid, error_message)
        """
        if provider == "zai":
            if model not in ZAI_AVAILABLE_MODELS:
                return False, f"Model '{model}' not available for Z.ai. Available: {', '.join(ZAI_AVAILABLE_MODELS)}"
            required_key = provider_requirements.get(provider)
            if required_key and not os.getenv(required_key):
                return False, f"Missing environment variable: {required_key}"
            return True, None

        # Qwen Cloud: validate model + credentials file (async)
        if provider == "qwen":
            from .constants import QWEN_AVAILABLE_MODELS
            if model not in QWEN_AVAILABLE_MODELS:
                return False, f"Model '{model}' not available for Qwen Cloud. Available: {', '.join(QWEN_AVAILABLE_MODELS)}"
            from .qwen_auth import QWEN_CREDS_PATH
            if not QWEN_CREDS_PATH.exists():
                return False, f"Qwen OAuth credentials not found at {QWEN_CREDS_PATH}. Run 'qwen' CLI to authenticate first."
            return True, None

        if provider in LOCAL_PROVIDER_CONFIG:
            base_url, endpoint, extract_models, start_hint = LOCAL_PROVIDER_CONFIG[provider]
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    response = await client.get(f"{base_url}{endpoint}")
                models = extract_models(response.json())
                if model not in models:
                    available = ", ".join(models[:10])
                    hint = f" (showing first 10)" if len(models) > 10 else ""
                    return False, f"Model '{model}' not found in {provider}. Available{hint}: {available}"
            except httpx.ConnectError:
                return False, f"{provider} service not running. Start with: {start_hint}"
            except httpx.TimeoutException:
                return False, f"{provider} service timeout. Check if service is running"
            except Exception as e:
                return False, f"Error checking {provider} availability: {str(e)}"
        elif provider in available_models:
            if model not in available_models[provider]:
                return False, f"Model {model} not available for {provider}. Available models: {', '.join(available_models[provider])}"
        else:
            return False, f"Unknown provider: {provider}. Available: {', '.join(list(available_models.keys()) + list(LOCAL_PROVIDER_CONFIG.keys()))}"

        required_key = provider_requirements.get(provider)
        if required_key and not os.getenv(required_key):
            return False, f"Missing environment variable: {required_key}"

        return True, None


async def _check_provider_health(provider: str) -> ProviderHealthStatus:
    """Check health of a single provider.

    Args:
        provider: Provider name (openai, anthropic, ollama, lmstudio, zai, qwen)

    Returns:
        ProviderHealthStatus with status, models, latency, and error
    """
    start_time = time.perf_counter()

    try:
        # OpenAI: API key check + authenticated GET /v1/models
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return ProviderHealthStatus(
                    status="down",
                    available_models=[],
                    error="Missing environment variable: OPENAI_API_KEY"
                )

            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    response = await client.get(
                        "https://api.openai.com/v1/models",
                        headers={"Authorization": f"Bearer {api_key}"}
                    )

                latency_ms = (time.perf_counter() - start_time) * 1000

                if response.status_code == 200:
                    # Parse model list from response
                    try:
                        data = response.json()
                        models = [m["id"] for m in data.get("data", [])]
                        return ProviderHealthStatus(
                            status="up",
                            available_models=models,
                            latency_ms=latency_ms
                        )
                    except Exception as e:
                        return ProviderHealthStatus(
                            status="down",
                            available_models=[],
                            latency_ms=latency_ms,
                            error=f"Error parsing response: {str(e)}"
                        )
                elif response.status_code in (401, 403):
                    return ProviderHealthStatus(
                        status="down",
                        available_models=[],
                        latency_ms=latency_ms,
                        error="API key invalid"
                    )
                else:
                    return ProviderHealthStatus(
                        status="down",
                        available_models=[],
                        latency_ms=latency_ms,
                        error=f"Unexpected status code: {response.status_code}"
                    )

            except httpx.ConnectError:
                return ProviderHealthStatus(
                    status="down",
                    available_models=[],
                    error="endpoint unreachable"
                )
            except httpx.TimeoutException:
                return ProviderHealthStatus(
                    status="down",
                    available_models=[],
                    error="openai endpoint timeout"
                )
            except Exception as e:
                return ProviderHealthStatus(
                    status="down",
                    available_models=[],
                    error=f"Error checking openai: {str(e)}"
                )

        # Anthropic: API key check only (no models endpoint)
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                return ProviderHealthStatus(
                    status="down",
                    available_models=[],
                    error="Missing environment variable: ANTHROPIC_API_KEY"
                )

            # Return static model list from constants
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ProviderHealthStatus(
                status="up",
                available_models=AVAILABLE_MODELS.get("anthropic", []),
                latency_ms=latency_ms
            )

        # Z.ai: API key check only (no models endpoint)
        elif provider == "zai":
            api_key = os.getenv("Z_AI_API_KEY")
            if not api_key:
                return ProviderHealthStatus(
                    status="down",
                    available_models=[],
                    error="Missing environment variable: Z_AI_API_KEY"
                )

            # Return static model list from constants
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ProviderHealthStatus(
                status="up",
                available_models=ZAI_AVAILABLE_MODELS,
                latency_ms=latency_ms
            )

        # Qwen Cloud: OAuth credentials file check + static model list
        elif provider == "qwen":
            from .qwen_auth import QWEN_CREDS_PATH
            if not QWEN_CREDS_PATH.exists():
                return ProviderHealthStatus(
                    status="down",
                    available_models=[],
                    error=f"Qwen OAuth credentials not found at {QWEN_CREDS_PATH}. Run 'qwen' CLI to authenticate first."
                )
            from .constants import QWEN_AVAILABLE_MODELS
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ProviderHealthStatus(
                status="up",
                available_models=QWEN_AVAILABLE_MODELS,
                latency_ms=latency_ms
            )

        # Ollama: Service running check + model list
        elif provider == "ollama":
            base_url, endpoint, extract_models, start_hint = LOCAL_PROVIDER_CONFIG[provider]
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    response = await client.get(f"{base_url}{endpoint}")

                latency_ms = (time.perf_counter() - start_time) * 1000
                models = extract_models(response.json())

                if not models:
                    return ProviderHealthStatus(
                        status="down",
                        available_models=[],
                        latency_ms=latency_ms
                    )

                # Check if all expected models are present
                expected_models = AVAILABLE_MODELS.get("ollama", [])
                missing_models = [m for m in expected_models if m not in models]

                if missing_models:
                    # Partial status - some models missing
                    return ProviderHealthStatus(
                        status="partial",
                        available_models=models,
                        latency_ms=latency_ms
                    )
                else:
                    return ProviderHealthStatus(
                        status="up",
                        available_models=models,
                        latency_ms=latency_ms
                    )

            except httpx.ConnectError:
                return ProviderHealthStatus(
                    status="down",
                    available_models=[],
                    error=f"{provider} service not running. Start with: {start_hint}"
                )
            except httpx.TimeoutException:
                return ProviderHealthStatus(
                    status="down",
                    available_models=[],
                    error=f"{provider} service timeout. Check if service is running"
                )
            except Exception as e:
                return ProviderHealthStatus(
                    status="down",
                    available_models=[],
                    error=f"Error checking {provider}: {str(e)}"
                )

        # LM Studio: Service running check + model list
        elif provider == "lmstudio":
            base_url, endpoint, extract_models, start_hint = LOCAL_PROVIDER_CONFIG[provider]
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    response = await client.get(f"{base_url}{endpoint}")

                latency_ms = (time.perf_counter() - start_time) * 1000
                models = extract_models(response.json())

                if not models:
                    return ProviderHealthStatus(
                        status="down",
                        available_models=[],
                        latency_ms=latency_ms
                    )

                return ProviderHealthStatus(
                    status="up",
                    available_models=models,
                    latency_ms=latency_ms
                )

            except httpx.ConnectError:
                return ProviderHealthStatus(
                    status="down",
                    available_models=[],
                    error=f"{provider} service not running. Start with: {start_hint}"
                )
            except httpx.TimeoutException:
                return ProviderHealthStatus(
                    status="down",
                    available_models=[],
                    error=f"{provider} service timeout. Check if service is running"
                )
            except Exception as e:
                return ProviderHealthStatus(
                    status="down",
                    available_models=[],
                    error=f"Error checking {provider}: {str(e)}"
                )

        else:
            return ProviderHealthStatus(
                status="down",
                available_models=[],
                error=f"Unknown provider: {provider}"
            )

    except Exception as e:
        logger.error(f"Unexpected error checking {provider}: {str(e)}")
        return ProviderHealthStatus(
            status="down",
            available_models=[],
            error=f"Error checking {provider}: {str(e)}"
        )


async def check_all_providers_async() -> CheckProvidersResponse:
    """Check health of all 6 providers concurrently.

    Returns:
        CheckProvidersResponse with status for all providers
    """
    start_time = time.perf_counter()

    providers = ["openai", "anthropic", "ollama", "lmstudio", "zai", "qwen"]
    tasks = [_check_provider_health(p) for p in providers]

    # Execute all checks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    providers_dict = {}
    up = down = partial = 0

    for provider, result in zip(providers, results):
        if isinstance(result, Exception):
            # Handle exception case
            providers_dict[provider] = ProviderHealthStatus(
                status="down",
                available_models=[],
                error=str(result)
            )
            down += 1
        else:
            # Result is ProviderHealthStatus
            providers_dict[provider] = result
            if result.status == "up":
                up += 1
            elif result.status == "down":
                down += 1
            elif result.status == "partial":
                partial += 1

    total_check_time_ms = (time.perf_counter() - start_time) * 1000

    logger.info(
        f"Health check completed: {up} up, {down} down, {partial} partial "
        f"in {total_check_time_ms:.1f}ms"
    )

    return CheckProvidersResponse(
        success=True,
        providers=providers_dict,
        total_check_time_ms=total_check_time_ms,
        providers_up=up,
        providers_down=down,
        providers_partial=partial
    )
